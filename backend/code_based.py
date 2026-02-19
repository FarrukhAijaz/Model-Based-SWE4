"""
C/C++ Code-Based SWE4 Module - Unit Testing & Analysis
========================================================
Handles C/C++ compilation unit testing with automated test generation
and execution. Mirrors the model-based workflow for consistency.

Features:
  - Upload .cc (source) and .h (header) files
  - Manage and validate header dependencies
  - Auto-generate test templates based on function signatures
  - Compile and run unit tests (using GoogleTest or similar)
  - Generate test reports and coverage analysis
"""

import os
import re
import json
import uuid
import shutil
import asyncio
import logging
import traceback
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from openpyxl import Workbook, load_workbook
except ImportError:
    Workbook = None
    load_workbook = None

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR
CODE_UPLOAD_DIR = BASE_DIR / "code_uploads"
CODE_OUTPUT_DIR = BASE_DIR / "code_outputs"
CODE_HEADERS_DIR = BASE_DIR / "stored_headers"  # Pre-stored headers
CODE_HEADERS_COMMON = CODE_HEADERS_DIR / "common"
CODE_HEADERS_FOCUS = CODE_HEADERS_DIR / "fcous"

CODE_UPLOAD_DIR.mkdir(exist_ok=True)
CODE_OUTPUT_DIR.mkdir(exist_ok=True)
CODE_HEADERS_DIR.mkdir(exist_ok=True)
CODE_HEADERS_COMMON.mkdir(exist_ok=True)
CODE_HEADERS_FOCUS.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("code_based_swe4")

# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------
code_job_store: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class CodeAnalysis(BaseModel):
    functions: List[Dict[str, Any]] = []
    missing_headers: List[str] = []
    available_headers: List[str] = []


class TestCase(BaseModel):
    function_name: str
    parameter_values: Dict[str, Any]
    expected_output: Optional[Any] = None


class CompileOptions(BaseModel):
    compiler: str = "g++"  # g++, clang++, msvc
    flags: str = "-std=c++11 -Wall"
    optimization: str = "-O0"  # No optimization for testing


# ---------------------------------------------------------------------------
# Create API router for code-based endpoints
# ---------------------------------------------------------------------------
router = APIRouter(
    prefix="/api/code-based",
    tags=["Code Based SWE4"],
    responses={404: {"description": "Not found"}},
)


# ---------------------------------------------------------------------------
# Code-Based Health & Status
# ---------------------------------------------------------------------------

@router.get("/health")
async def code_based_health():
    """Check Code-based SWE4 module health."""
    return {
        "status": "available",
        "module": "code-based-swe4",
        "version": "2.0.0",
        "message": "C/C++ unit testing with automated test generation",
        "features": [
            "Upload .cc and .h files",
            "Auto-analyze function signatures",
            "Validate header dependencies",
            "Generate test templates",
            "Compile and run unit tests",
            "Code coverage measurement",
        ],
    }


@router.get("/available-headers")
async def get_available_headers():
    """Get list of pre-stored headers available on backend."""
    common_headers = []
    focus_headers = []
    
    if CODE_HEADERS_COMMON.exists():
        common_headers = [f.name for f in CODE_HEADERS_COMMON.glob("*.h")]
    
    if CODE_HEADERS_FOCUS.exists():
        focus_headers = [f.name for f in CODE_HEADERS_FOCUS.glob("*.h")]
    
    return {
        "common": sorted(common_headers),
        "focus": sorted(focus_headers),
    }


# ---------------------------------------------------------------------------
# Helper Functions: Code Analysis
# ---------------------------------------------------------------------------

def extract_functions_from_source(source_content: str) -> List[Dict[str, Any]]:
    """
    Parse C/C++ source file to extract function signatures.
    Returns list of function metadata with name, return type, and parameters.
    """
    functions = []
    
    # Regex to match function definitions (simple pattern)
    # Matches: returnType functionName(params)
    pattern = r'(?:^|\n)\s*(\w+(?:\s+\*)?)\s+(\w+)\s*\(([^)]*)\)\s*(?:{|;)'
    
    matches = re.finditer(pattern, source_content, re.MULTILINE)
    
    for match in matches:
        return_type = match.group(1).strip()
        func_name = match.group(2).strip()
        params_str = match.group(3).strip()
        
        # Parse parameters
        params = []
        if params_str and params_str != "void":
            for param in params_str.split(','):
                param = param.strip()
                if param:
                    # Extract type and name
                    parts = param.rsplit(' ', 1)
                    if len(parts) == 2:
                        param_type, param_name = parts
                        params.append({
                            "name": param_name.replace('*', '').strip(),
                            "type": param_type.strip(),
                        })
        
        functions.append({
            "name": func_name,
            "returnType": return_type,
            "parameters": params,
        })
    
    return functions


def extract_includes_from_source(source_content: str) -> Tuple[List[str], List[str]]:
    """
    Extract #include directives from source file.
    Returns tuple of (system_includes, local_includes)
    """
    system_includes = []
    local_includes = []
    
    # Match #include <...> and #include "..."
    include_pattern = r'#include\s+[<"]([^>"]+)[>"]'
    
    matches = re.finditer(include_pattern, source_content)
    for match in matches:
        include = match.group(1)
        if source_content[match.start():match.start()+8].strip().endswith('<'):
            system_includes.append(include)
        else:
            local_includes.append(include)
    
    return system_includes, local_includes


def find_missing_headers(local_includes: List[str], session_dir: Path) -> Tuple[List[str], List[str]]:
    """
    Check which local headers are missing.
    Check in session dir first, then in pre-stored header directories (common, fcous).
    Returns tuple of (available_headers, missing_headers)
    """
    available = []
    missing = []
    
    for header in local_includes:
        # Check session directory first
        header_path = session_dir / header
        if header_path.exists():
            available.append(header)
            continue
        
        # Check pre-stored directories
        common_header = CODE_HEADERS_COMMON / header
        focus_header = CODE_HEADERS_FOCUS / header
        
        if common_header.exists():
            available.append(f"{header} (common)")
            continue
        
        if focus_header.exists():
            available.append(f"{header} (focus)")
            continue
        
        # Not found anywhere
        missing.append(header)
    
    return available, missing


# ---------------------------------------------------------------------------
# Test Template Generation
# ---------------------------------------------------------------------------

def generate_cpp_test_template(
    session_dir: Path,
    unit_name: str,
    functions: List[Dict[str, Any]],
) -> Path:
    """
    Generate a test data Excel template for C/C++ unit testing.
    Similar to the Simulink template but for function parameters and returns.
    """
    if Workbook is None:
        raise RuntimeError("openpyxl is not installed — cannot generate Excel template")
    
    wb = Workbook()
    
    for func_idx, func in enumerate(functions):
        sheet_name = f"{func['name']}_Test"[:31]  # Max 31 chars for Excel sheets
        
        if func_idx == 0:
            ws = wb.active
            ws.title = sheet_name
        else:
            ws = wb.create_sheet(title=sheet_name)
        
        # Header row
        headers = ["Test_Case_ID", "Description"]
        
        # Add parameter columns
        for param in func['parameters']:
            headers.append(f"Param_{param['name']}({param['type']})")
        
        # Add expected output column
        headers.append(f"Expected_Output({func['returnType']})")
        
        for col_idx, header in enumerate(headers, 1):
            ws.cell(row=1, column=col_idx, value=header)
        
        # Add 5 empty test case rows
        for tc_idx in range(1, 6):
            ws.cell(row=tc_idx + 1, column=1, value=f"TC_{tc_idx:03d}")
            ws.cell(row=tc_idx + 1, column=2, value=f"Test case {tc_idx}")
            # User fills in the rest
    
    excel_filename = f"{unit_name}_TestData.xlsx"
    excel_path = session_dir / excel_filename
    wb.save(str(excel_path))
    logger.info(f"Generated C/C++ test template: {excel_path}")
    
    return excel_path


# ---------------------------------------------------------------------------
# Upload & Analysis Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_code_files(
    unit_file: UploadFile = File(..., description="C/C++ .cc or .cpp source file"),
    header_file: UploadFile = File(..., description="C/C++ .h header file"),
):
    """
    Phase 1: Upload unit .cc file and corresponding header file.
    Validates file extensions and creates session directory.
    """
    # Validate extensions
    if not unit_file.filename.endswith((".cc", ".cpp", ".c")):
        raise HTTPException(400, "Unit file must be a .cc, .cpp, or .c file")
    
    if not header_file.filename.endswith((".h", ".hpp")):
        raise HTTPException(400, "Header file must be a .h or .hpp file")
    
    # Create session
    session_id = str(uuid.uuid4())[:8]
    session_dir = CODE_UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # Save files
    unit_path = session_dir / unit_file.filename
    header_path = session_dir / header_file.filename
    
    try:
        with open(unit_path, "wb") as f:
            content = await unit_file.read()
            f.write(content)
        
        with open(header_path, "wb") as f:
            content = await header_file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(500, f"Failed to save uploaded files: {e}")
    
    logger.info(f"Files uploaded: session={session_id}, unit={unit_file.filename}, header={header_file.filename}")
    
    return {
        "session_id": session_id,
        "unit_file": unit_file.filename,
        "header_file": header_file.filename,
        "message": "Files uploaded successfully. Call /analyze/{session_id} to continue.",
    }


@router.post("/analyze/{session_id}")
async def analyze_code(session_id: str):
    """
    Phase 2: Analyze uploaded C/C++ code.
    Extract function signatures, identify header dependencies, check for missing headers.
    """
    session_dir = CODE_UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")
    
    # Find source file
    source_files = list(session_dir.glob("*.cc")) + list(session_dir.glob("*.cpp"))
    if not source_files:
        raise HTTPException(400, "No .cc or .cpp source file found")
    
    source_path = source_files[0]
    source_name = source_path.stem
    
    try:
        with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
            source_content = f.read()
    except Exception as e:
        raise HTTPException(500, f"Failed to read source file: {e}")
    
    # Extract functions
    functions = extract_functions_from_source(source_content)
    
    # Extract includes
    system_includes, local_includes = extract_includes_from_source(source_content)
    
    # Check for missing headers
    available_headers, missing_headers = find_missing_headers(local_includes, session_dir)
    
    analysis_result = {
        "session_id": session_id,
        "unit_name": source_name,
        "functions": functions,
        "system_includes": system_includes,
        "local_includes": local_includes,
        "available_headers": available_headers,
        "missing_headers": missing_headers,
        "headers_needed": len(missing_headers) > 0,
    }
    
    # Save analysis
    meta_path = session_dir / "_analysis.json"
    with open(meta_path, 'w') as f:
        json.dump(analysis_result, f, indent=2)
    
    logger.info(f"Code analysis complete: session={session_id}, functions={len(functions)}, missing_headers={len(missing_headers)}")
    
    return analysis_result


@router.post("/upload-missing-headers/{session_id}")
async def upload_missing_headers(
    session_id: str,
    header_files: List[UploadFile] = File(..., description="Missing header files"),
):
    """
    Phase 2b: Upload missing headers if analysis detected any.
    User provides the additional headers needed for compilation.
    """
    session_dir = CODE_UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")
    
    saved_headers = []
    try:
        for header_file in header_files:
            if not header_file.filename.endswith((".h", ".hpp")):
                continue
            
            header_path = session_dir / header_file.filename
            with open(header_path, "wb") as f:
                content = await header_file.read()
                f.write(content)
            
            saved_headers.append(header_file.filename)
    except Exception as e:
        raise HTTPException(500, f"Failed to save header files: {e}")
    
    logger.info(f"Additional headers uploaded: session={session_id}, headers={saved_headers}")
    
    return {
        "session_id": session_id,
        "headers_uploaded": saved_headers,
        "message": f"Uploaded {len(saved_headers)} header files. Call /generate-template/{session_id} to proceed.",
    }


@router.post("/generate-template/{session_id}")
async def generate_template(session_id: str):
    """
    Phase 3: Generate test template Excel based on extracted functions.
    User will fill in test data (parameters and expected outputs).
    """
    session_dir = CODE_UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")
    
    # Load analysis
    meta_path = session_dir / "_analysis.json"
    if not meta_path.exists():
        raise HTTPException(400, "Code analysis not found. Call /analyze/{session_id} first.")
    
    try:
        with open(meta_path) as f:
            analysis = json.load(f)
    except Exception as e:
        raise HTTPException(500, f"Failed to load analysis: {e}")
    
    if not analysis.get('functions'):
        raise HTTPException(400, "No functions found to test")
    
    # Generate test template
    try:
        excel_path = generate_cpp_test_template(
            session_dir,
            analysis['unit_name'],
            analysis['functions']
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to generate test template: {e}")
    
    return {
        "session_id": session_id,
        "template_file": excel_path.name,
        "functions_count": len(analysis['functions']),
        "message": "Test template generated. Please fill in test data and upload back.",
    }


@router.post("/upload-test-data/{session_id}")
async def upload_test_data(
    session_id: str,
    test_data_file: UploadFile = File(..., description="Filled test data Excel file"),
):
    """
    Phase 4: Upload filled test data Excel file.
    Validates the test data format.
    """
    session_dir = CODE_UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")
    
    if not test_data_file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Test data file must be .xlsx or .xls")
    
    # Save test data
    test_data_path = session_dir / "TestData.xlsx"
    try:
        with open(test_data_path, "wb") as f:
            content = await test_data_file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(500, f"Failed to save test data: {e}")
    
    logger.info(f"Test data uploaded: session={session_id}")
    
    return {
        "session_id": session_id,
        "test_data_file": "TestData.xlsx",
        "message": "Test data uploaded successfully. Call /compile-and-test/{session_id} to proceed.",
    }


# ---------------------------------------------------------------------------
# Compilation & Test Execution
# ---------------------------------------------------------------------------

@router.post("/compile-and-test/{session_id}")
async def compile_and_test(
    session_id: str,
    background_tasks: BackgroundTasks,
    options: Optional[CompileOptions] = None,
):
    """
    Phase 5: Trigger compilation and test execution.
    Runs as a background job. Returns job_id for status polling.
    """
    session_dir = CODE_UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")
    
    # Verify all required files exist
    source_files = list(session_dir.glob("*.cc")) + list(session_dir.glob("*.cpp"))
    if not source_files:
        raise HTTPException(400, "No source file found")
    
    if not (session_dir / "TestData.xlsx").exists():
        raise HTTPException(400, "No test data found. Upload test data first.")
    
    job_id = str(uuid.uuid4())[:8]
    job_dir = CODE_OUTPUT_DIR / session_id / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    now = datetime.utcnow().isoformat()
    code_job_store[job_id] = {
        "job_id": job_id,
        "session_id": session_id,
        "status": "pending",
        "progress": 0,
        "current_phase": "Queued",
        "message": "Test job queued",
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "source_path": str(source_files[0]),
        "test_data_path": str(session_dir / "TestData.xlsx"),
        "output_dir": str(job_dir),
        "options": options.model_dump() if options else {},
    }
    
    background_tasks.add_task(execute_code_tests, job_id)
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Test job queued for compilation and execution",
    }


async def execute_code_tests(job_id: str):
    """Background task: Compile and run C/C++ tests."""
    job = code_job_store[job_id]
    session_id = job['session_id']
    source_path = job['source_path']
    test_data_path = job['test_data_path']
    output_dir = job['output_dir']
    opts = job['options']
    
    def update_job(status, progress, phase, message, **kwargs):
        job["status"] = status
        job["progress"] = progress
        job["current_phase"] = phase
        job["message"] = message
        job["updated_at"] = datetime.utcnow().isoformat()
        job.update(kwargs)
        logger.info(f"[Job {job_id}] {phase}: {message} ({progress}%)")
    
    try:
        update_job("running", 10, "Preparation", "Preparing for compilation...")
        
        session_dir = CODE_UPLOAD_DIR / session_id
        
        # Load test data
        update_job("running", 20, "Test Setup", "Parsing test data...")
        try:
            wb = load_workbook(test_data_path, data_only=True)
            test_sheets = wb.sheetnames
            num_tests = len(test_sheets)
        except Exception as e:
            update_job("error", 0, "Test Setup", f"Failed to parse test data: {e}", error=str(e))
            return
        
        # Compile
        update_job("running", 30, "Compilation", "Compiling C/C++ code...")
        
        compiler = opts.get('compiler', 'g++')
        flags = opts.get('flags', '-std=c++11 -Wall')
        optimization = opts.get('optimization', '-O0')
        
        output_binary = Path(output_dir) / "test_unit"
        
        compile_cmd = [
            compiler,
            str(source_path),
            flags,
            optimization,
            "-o", str(output_binary),
            f"-I{session_dir}",  # Include session headers
            f"-I{CODE_HEADERS_COMMON}",  # Include common headers
            f"-I{CODE_HEADERS_FOCUS}",  # Include focus headers
        ]
        
        try:
            result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                update_job("error", 40, "Compilation", f"Compilation failed: {error_msg}", error=error_msg)
                return
            
            logger.info(f"Compilation successful: {output_binary}")
        except subprocess.TimeoutExpired:
            update_job("error", 40, "Compilation", "Compilation timed out", error="Timeout")
            return
        except Exception as e:
            update_job("error", 40, "Compilation", f"Compilation error: {e}", error=str(e))
            return
        
        # Execution
        update_job("running", 60, "Execution", "Running test cases...")
        
        try:
            result = subprocess.run(
                [str(output_binary)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            execution_output = result.stdout + result.stderr
            
            # Save execution log
            log_path = Path(output_dir) / "execution.log"
            with open(log_path, 'w') as f:
                f.write(execution_output)
            
            logger.info(f"Test execution completed: {job_id}")
        except subprocess.TimeoutExpired:
            update_job("error", 70, "Execution", "Test execution timed out", error="Timeout")
            return
        except Exception as e:
            update_job("error", 70, "Execution", f"Execution error: {e}", error=str(e))
            return
        
        # Generate report
        update_job("running", 80, "Report Generation", "Generating test report...")
        
        report = {
            "job_id": job_id,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "source_file": Path(source_path).name,
            "num_test_cases": num_tests,
            "compiler": compiler,
            "compilation_status": "passed",
            "execution_status": "completed",
            "execution_output": execution_output[:1000],  # First 1000 chars
        }
        
        report_path = Path(output_dir) / "report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        update_job(
            "completed",
            100,
            "Complete",
            "Test execution and report generation complete",
            result=report,
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in test execution: {e}\n{traceback.format_exc()}")
        update_job("error", 0, "Error", f"Unexpected error: {e}", error=str(e))


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a code-based test job."""
    if job_id not in code_job_store:
        raise HTTPException(404, f"Job {job_id} not found")
    
    return code_job_store[job_id]


@router.get("/download-report/{session_id}/{job_id}")
async def download_report(session_id: str, job_id: str):
    """Download test report and execution artifacts."""
    report_path = CODE_OUTPUT_DIR / session_id / job_id / "report.json"
    
    if not report_path.exists():
        raise HTTPException(404, "Report not found")
    
    return FileResponse(str(report_path), filename="report.json")
