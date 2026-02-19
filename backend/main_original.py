"""
Simulink Test Automation - FastAPI Backend
==========================================
Connects to a shared MATLAB session and orchestrates Simulink unit testing
via the MATLAB Engine API for Python.

Prerequisites:
    - MATLAB with Simulink, Simulink Test, and Simulink Coverage licenses
    - MATLAB Engine API for Python installed
    - A shared MATLAB session running (run `matlab.engine.shareEngine` in MATLAB)

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import sys
import json
import shutil
import asyncio
import logging
import traceback
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR.parent  # /home/saijaz/Desktop/Simulink
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
MATLAB_SCRIPTS_DIR = BASE_DIR / "matlab_scripts"

# Known sample model in the workspace root
SAMPLE_MODEL = WORKSPACE_DIR / "SimulinkSample.slx"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("simulink_automation")

# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------
matlab_engine = None
job_store: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# MATLAB Engine Helpers
# ---------------------------------------------------------------------------
def get_matlab_engine():
    """Return the cached MATLAB engine, connecting on first use."""
    global matlab_engine
    if matlab_engine is not None:
        try:
            # Quick health check
            matlab_engine.eval("1;", nargout=0)
            return matlab_engine
        except Exception:
            logger.warning("MATLAB engine connection lost. Reconnecting...")
            matlab_engine = None

    try:
        import matlab.engine  # type: ignore

        # Try to find shared sessions
        sessions = matlab.engine.find_matlab()
        if not sessions:
            raise RuntimeError(
                "No shared MATLAB session found. "
                "Please run `matlab.engine.shareEngine` in your MATLAB Command Window."
            )
        logger.info(f"Found shared MATLAB sessions: {sessions}")
        matlab_engine = matlab.engine.connect_matlab(sessions[0])
        logger.info(f"Connected to MATLAB session: {sessions[0]}")

        # Add our helper scripts to the MATLAB path
        matlab_engine.addpath(str(MATLAB_SCRIPTS_DIR), nargout=0)
        logger.info(f"Added MATLAB scripts path: {MATLAB_SCRIPTS_DIR}")

        return matlab_engine
    except ImportError:
        raise RuntimeError(
            "matlab.engine Python package is not installed. "
            "Run: cd <MATLAB_ROOT>/extern/engines/python && python setup.py install"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to connect to MATLAB: {e}")


def check_matlab_licenses(eng) -> dict:
    """Check availability of required MATLAB toolbox licenses."""
    licenses = {}
    for toolbox in ["Simulink", "Simulink_Test", "Simulink_Coverage"]:
        try:
            result = eng.eval(f"license('test', '{toolbox}')", nargout=1)
            licenses[toolbox] = bool(result)
        except Exception:
            licenses[toolbox] = False
    return licenses


def matlab_struct_to_dict(eng, matlab_var_name: str) -> dict:
    """Convert a MATLAB struct (stored in a workspace variable) to a Python dict via JSON."""
    try:
        json_str = eng.eval(f"jsonencode({matlab_var_name})", nargout=1)
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Error converting MATLAB struct to dict: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class JobStatus(BaseModel):
    job_id: str
    status: str  # pending | running | phase1 | phase2 | phase3 | phase4 | completed | error
    progress: int  # 0-100
    current_phase: str
    message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class RunOptions(BaseModel):
    cleanup_harness: bool = False
    cleanup_test_file: bool = False
    stop_time: str = ""
    fixed_step: str = ""


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Simulink Test Automation Server")
    yield
    logger.info("Shutting down...")
    global matlab_engine
    if matlab_engine is not None:
        try:
            matlab_engine.quit()
        except Exception:
            pass
        matlab_engine = None


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Simulink Test Automation",
    description="Automates Simulink unit testing via MATLAB Engine API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health_check():
    """Check server and MATLAB connectivity."""
    matlab_connected = False
    matlab_sessions = []
    licenses = {}

    try:
        import matlab.engine  # type: ignore
        matlab_sessions = list(matlab.engine.find_matlab())
    except ImportError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "matlab.engine Python package not installed",
                "matlab_connected": False,
            },
        )
    except Exception:
        pass

    try:
        eng = get_matlab_engine()
        matlab_connected = True
        licenses = check_matlab_licenses(eng)
    except Exception as e:
        return JSONResponse(
            content={
                "status": "degraded",
                "message": str(e),
                "matlab_connected": False,
                "available_sessions": matlab_sessions,
                "licenses": licenses,
            }
        )

    return {
        "status": "ok",
        "matlab_connected": matlab_connected,
        "available_sessions": matlab_sessions,
        "licenses": licenses,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/sample-files")
async def get_sample_files():
    """Check if sample model (SimulinkSample.slx) exists in the workspace."""
    model_exists = SAMPLE_MODEL.exists()
    return {
        "model_available": model_exists,
        "model_name": SAMPLE_MODEL.name if model_exists else None,
    }


@app.post("/api/use-sample")
async def use_sample_files():
    """
    Create a session using the pre-existing SimulinkSample.slx from the workspace
    directory — no file upload required. Test data Excel is auto-generated later.
    """
    if not SAMPLE_MODEL.exists():
        raise HTTPException(404, f"Sample model not found at {SAMPLE_MODEL}")

    session_id = str(uuid.uuid4())[:8]
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Copy model (not symlink) so the session dir is self-contained
    model_dest = session_dir / SAMPLE_MODEL.name
    shutil.copy2(SAMPLE_MODEL, model_dest)

    logger.info(f"Sample model loaded: session={session_id}, model={SAMPLE_MODEL.name}")

    return {
        "session_id": session_id,
        "model_file": SAMPLE_MODEL.name,
        "model_path": str(model_dest),
    }


@app.post("/api/upload")
async def upload_files(
    model_file: UploadFile = File(..., description="Simulink .slx model file"),
    test_data_file: Optional[UploadFile] = File(None, description="Optional Excel .xlsx test data file"),
):
    """Upload model (.slx) file. Test data Excel is optional (auto-generated if not provided)."""
    # Validate extensions
    if not model_file.filename.endswith(".slx"):
        raise HTTPException(400, "Model file must be a .slx file")
    if test_data_file and not test_data_file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Test data file must be an .xlsx or .xls file")

    # Create a unique session directory
    session_id = str(uuid.uuid4())[:8]
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Save files
    model_path = session_dir / model_file.filename

    try:
        with open(model_path, "wb") as f:
            content = await model_file.read()
            f.write(content)

        result = {
            "session_id": session_id,
            "model_file": model_file.filename,
            "model_path": str(model_path),
        }

        if test_data_file:
            excel_path = session_dir / test_data_file.filename
            with open(excel_path, "wb") as f:
                content = await test_data_file.read()
                f.write(content)
            result["test_data_file"] = test_data_file.filename
            result["excel_path"] = str(excel_path)

    except Exception as e:
        raise HTTPException(500, f"Failed to save uploaded files: {e}")

    logger.info(f"Files uploaded: session={session_id}, model={model_file.filename}")

    return result


@app.post("/api/analyze/{session_id}")
async def analyze_model(session_id: str):
    """Phase 1: Open the model and identify inputs/outputs."""
    session_dir = UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")

    # Find .slx file
    slx_files = list(session_dir.glob("*.slx"))
    if not slx_files:
        raise HTTPException(400, "No .slx model file found in session")
    model_path = slx_files[0]
    model_name = model_path.stem

    try:
        eng = get_matlab_engine()
    except Exception as e:
        raise HTTPException(503, f"MATLAB connection failed: {e}")

    try:
        # Check licenses first
        licenses = check_matlab_licenses(eng)

        # Add upload directory to MATLAB path
        eng.addpath(str(session_dir), nargout=0)

        # Close any previously loaded model with the same name
        try:
            eng.close_system(model_name, 0.0, nargout=0)
            logger.info(f"Closed previously loaded model: {model_name}")
        except Exception:
            pass  # Model wasn't loaded — safe to ignore

        # Load the model
        eng.load_system(str(model_path), nargout=0)

        # Get inputs
        inport_blocks = eng.find_system(
            model_name, "SearchDepth", 1.0, "BlockType", "Inport", nargout=1
        )
        inputs = []
        if inport_blocks:
            if isinstance(inport_blocks, str):
                inport_blocks = [inport_blocks]
            for block in inport_blocks:
                name = eng.get_param(block, "Name", nargout=1)
                port = eng.get_param(block, "Port", nargout=1)
                dtype = eng.get_param(block, "OutDataTypeStr", nargout=1)
                inputs.append({
                    "name": name,
                    "port": port,
                    "dataType": dtype,
                })

        # Get outputs
        outport_blocks = eng.find_system(
            model_name, "SearchDepth", 1.0, "BlockType", "Outport", nargout=1
        )
        outputs = []
        if outport_blocks:
            if isinstance(outport_blocks, str):
                outport_blocks = [outport_blocks]
            for block in outport_blocks:
                name = eng.get_param(block, "Name", nargout=1)
                port = eng.get_param(block, "Port", nargout=1)
                dtype = eng.get_param(block, "OutDataTypeStr", nargout=1)
                outputs.append({
                    "name": name,
                    "port": port,
                    "dataType": dtype,
                })

        # Get solver info
        stop_time = eng.get_param(model_name, "StopTime", nargout=1)
        fixed_step = eng.get_param(model_name, "FixedStep", nargout=1)
        solver = eng.get_param(model_name, "SolverName", nargout=1)

        analysis_result = {
            "model_name": model_name,
            "inputs": inputs,
            "outputs": outputs,
            "solver": solver,
            "stop_time": stop_time,
            "fixed_step": fixed_step,
            "licenses": licenses,
        }

        # Save analysis metadata for later validation of uploaded test data
        meta_path = session_dir / "_analysis.json"
        with open(meta_path, "w") as f:
            json.dump(analysis_result, f)

        return analysis_result

    except Exception as e:
        logger.error(f"Model analysis failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"Model analysis failed: {e}")


# ---------------------------------------------------------------------------
# Simulink Test-compliant Excel Template Generation
# ---------------------------------------------------------------------------
def generate_simulink_test_excel(
    session_dir: Path,
    model_name: str,
    inputs: list,
    outputs: list,
    stop_time: str,
    num_scenarios: int = 5,
    start_time: float = 0.0,
    time_step: float = None,
) -> Path:
    """
    Generate a Simulink Test-compliant Excel file with dummy test data.

    Format per the Simulink Test documentation (page 6-84, "Create External Data
    Files to Use in Test Cases"):
      - Each sheet = one test scenario / iteration
      - Column A: Time
      - Columns B+: Input signal data (column names = Inport block names)

    The file can be referenced in a test case using:
      tc.setProperty('IsTestDataReferenced', true);
      tc.setProperty('TestDataPath', '<path>');

    Returns the path to the generated Excel file.
    """
    if Workbook is None:
        raise RuntimeError("openpyxl is not installed — cannot generate Excel template")

    wb = Workbook()
    input_names = [inp["name"] for inp in inputs]
    output_names = [out["name"] for out in outputs]

    try:
        t_stop = float(stop_time)
    except (ValueError, TypeError):
        t_stop = 10.0

    t_start = float(start_time) if start_time is not None else 0.0

    # Build time vector based on user-specified time step or default 5 points
    if time_step is not None and time_step > 0:
        import math
        time_points = []
        t = t_start
        while t <= t_stop + 1e-12:
            time_points.append(round(t, 10))
            t += time_step
        # Ensure the stop time is included
        if len(time_points) == 0 or abs(time_points[-1] - t_stop) > 1e-12:
            time_points.append(t_stop)
    else:
        # Default: 5 evenly spaced points
        time_points = [
            t_start,
            t_start + (t_stop - t_start) / 4,
            t_start + (t_stop - t_start) / 2,
            t_start + 3 * (t_stop - t_start) / 4,
            t_stop,
        ]

    # All scenarios default to 0 — user fills in actual values + expected outputs
    for sc_idx in range(num_scenarios):
        sheet_name = f"Scenario_{sc_idx + 1}"

        if sc_idx == 0:
            ws = wb.active
            ws.title = sheet_name
        else:
            ws = wb.create_sheet(title=sheet_name)

        # Header: Time, <inputs...>, Expected_<outputs...>
        expected_output_names = [f"Expected_{o}" for o in output_names]
        headers = ["Time"] + input_names + expected_output_names
        for col_idx, header in enumerate(headers, 1):
            ws.cell(row=1, column=col_idx, value=header)

        for row_idx, t in enumerate(time_points, 2):
            ws.cell(row=row_idx, column=1, value=t)
            # Input columns: default 0
            for col_idx in range(len(input_names)):
                ws.cell(row=row_idx, column=col_idx + 2, value=0)
            # Expected output columns: default 0
            offset = 2 + len(input_names)
            for col_idx in range(len(output_names)):
                ws.cell(row=row_idx, column=offset + col_idx, value=0)

    excel_filename = f"{model_name}_TestData.xlsx"
    excel_path = session_dir / excel_filename
    wb.save(str(excel_path))
    logger.info(f"Generated Simulink Test-compliant Excel: {excel_path} ({num_scenarios} scenarios, {len(time_points)} time points)")

    return excel_path


class GenerateTemplateRequest(BaseModel):
    num_scenarios: int = 5
    start_time: Optional[float] = None
    stop_time: Optional[float] = None
    time_step: Optional[float] = None


@app.post("/api/generate-template/{session_id}")
async def generate_template(session_id: str, request: Optional[GenerateTemplateRequest] = None):
    """
    Generate a Simulink Test-compliant Excel template with dummy test data.
    Requires the model to have been analyzed first (calls analyze internally).
    """
    session_dir = UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")

    slx_files = list(session_dir.glob("*.slx"))
    if not slx_files:
        raise HTTPException(400, "No .slx model file found in session")
    model_path = slx_files[0]
    model_name = model_path.stem

    try:
        eng = get_matlab_engine()
    except Exception as e:
        raise HTTPException(503, f"MATLAB connection failed: {e}")

    try:
        # Ensure model is loaded and get I/O info
        eng.addpath(str(session_dir), nargout=0)
        try:
            eng.close_system(model_name, 0.0, nargout=0)
        except Exception:
            pass

        eng.load_system(str(model_path), nargout=0)

        # Get inputs
        inport_blocks = eng.find_system(
            model_name, "SearchDepth", 1.0, "BlockType", "Inport", nargout=1
        )
        inputs = []
        if inport_blocks:
            blocks = inport_blocks if isinstance(inport_blocks, list) else [inport_blocks]
            for block in blocks:
                inputs.append({
                    "name": eng.get_param(block, "Name", nargout=1),
                    "port": eng.get_param(block, "Port", nargout=1),
                    "dataType": eng.get_param(block, "OutDataTypeStr", nargout=1),
                })

        # Get outputs
        outport_blocks = eng.find_system(
            model_name, "SearchDepth", 1.0, "BlockType", "Outport", nargout=1
        )
        outputs = []
        if outport_blocks:
            blocks = outport_blocks if isinstance(outport_blocks, list) else [outport_blocks]
            for block in blocks:
                outputs.append({
                    "name": eng.get_param(block, "Name", nargout=1),
                    "port": eng.get_param(block, "Port", nargout=1),
                    "dataType": eng.get_param(block, "OutDataTypeStr", nargout=1),
                })

        stop_time = eng.get_param(model_name, "StopTime", nargout=1)

        num_scenarios = 5
        user_start_time = 0.0
        user_stop_time = None
        user_time_step = None
        if request:
            if request.num_scenarios:
                num_scenarios = max(1, min(request.num_scenarios, 100))
            if request.start_time is not None:
                user_start_time = request.start_time
            if request.stop_time is not None:
                user_stop_time = request.stop_time
            if request.time_step is not None:
                user_time_step = request.time_step

        # User-specified stop time overrides the model's stop time
        effective_stop_time = str(user_stop_time) if user_stop_time is not None else stop_time

        excel_path = generate_simulink_test_excel(
            session_dir=session_dir,
            model_name=model_name,
            inputs=inputs,
            outputs=outputs,
            stop_time=effective_stop_time,
            num_scenarios=num_scenarios,
            start_time=user_start_time,
            time_step=user_time_step,
        )

        return {
            "session_id": session_id,
            "template_file": excel_path.name,
            "template_path": str(excel_path),
            "num_scenarios": num_scenarios,
            "inputs": [inp["name"] for inp in inputs],
            "outputs": [out["name"] for out in outputs],
            "stop_time": effective_stop_time,
            "message": f"Generated {num_scenarios} test scenarios with dummy data. "
                       "Download and edit the template, or use as-is.",
        }
    except Exception as e:
        logger.error(f"Template generation failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"Template generation failed: {e}")


@app.get("/api/download/template/{session_id}")
async def download_template(session_id: str):
    """Download the generated Simulink Test-compliant Excel template."""
    session_dir = UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")

    # Look for the generated template
    xlsx_files = list(session_dir.glob("*_TestData.xlsx"))
    if not xlsx_files:
        raise HTTPException(404, "No generated template found. Call /api/generate-template first.")

    return FileResponse(
        xlsx_files[0],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=xlsx_files[0].name,
    )


@app.post("/api/upload-test-data/{session_id}")
async def upload_test_data(
    session_id: str,
    test_data_file: UploadFile = File(..., description="Simulink Test-compliant Excel file"),
):
    """Upload a custom test data Excel to replace the generated template.
    Automatically validates the file after saving."""
    session_dir = UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")

    if not test_data_file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Test data file must be an .xlsx or .xls file")

    # Remove existing test data files
    for old in session_dir.glob("*_TestData.xlsx"):
        old.unlink()

    model_name = None
    slx_files = list(session_dir.glob("*.slx"))
    if slx_files:
        model_name = slx_files[0].stem

    # Save with standardized name
    dest_name = f"{model_name}_TestData.xlsx" if model_name else test_data_file.filename
    dest_path = session_dir / dest_name

    try:
        with open(dest_path, "wb") as f:
            content = await test_data_file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(500, f"Failed to save test data: {e}")

    logger.info(f"Custom test data uploaded: session={session_id}, file={dest_name}")

    # Auto-validate the uploaded file
    validation = _validate_test_data_excel(dest_path, session_id)

    return {
        "session_id": session_id,
        "test_data_file": dest_name,
        "message": "Custom test data uploaded successfully.",
        "validation": validation,
    }


def _validate_test_data_excel(excel_path: Path, session_id: str) -> dict:
    """Validate a test data Excel file: check sheets, columns, and data completeness."""
    from openpyxl import load_workbook

    result = {
        "valid": True,
        "num_scenarios": 0,
        "sheets": [],
        "errors": [],
        "warnings": [],
    }

    try:
        wb = load_workbook(str(excel_path), data_only=True)
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"Cannot open Excel file: {e}")
        return result

    if len(wb.sheetnames) == 0:
        result["valid"] = False
        result["errors"].append("Excel file has no sheets.")
        return result

    # Determine expected input columns from the model analysis stored on disk
    # We look at the existing analysis or infer from the first sheet
    expected_inputs = None
    expected_outputs = None
    # Try to find the analysis stored in the session metadata
    session_dir = UPLOAD_DIR / session_id
    meta_path = session_dir / "_analysis.json"
    if meta_path.exists():
        try:
            import json as _json
            with open(meta_path) as f:
                meta = _json.load(f)
            expected_inputs = [inp["name"] for inp in meta.get("inputs", [])]
            expected_outputs = [out["name"] for out in meta.get("outputs", [])]
        except Exception:
            pass

    result["num_scenarios"] = len(wb.sheetnames)

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        sheet_info = {
            "name": sheet_name,
            "rows": ws.max_row - 1 if ws.max_row and ws.max_row > 1 else 0,
            "columns": [],
            "errors": [],
            "warnings": [],
        }

        # Read header row
        headers = []
        for col in range(1, (ws.max_column or 0) + 1):
            val = ws.cell(row=1, column=col).value
            if val is not None:
                headers.append(str(val))
        sheet_info["columns"] = headers

        if not headers:
            sheet_info["errors"].append("Sheet has no header row.")
            result["valid"] = False
            result["sheets"].append(sheet_info)
            continue

        # Check Time column
        if "Time" not in headers:
            sheet_info["errors"].append("Missing required 'Time' column.")
            result["valid"] = False

        # Check expected input columns
        if expected_inputs:
            for inp_name in expected_inputs:
                if inp_name not in headers:
                    sheet_info["errors"].append(f"Missing expected input column: '{inp_name}'.")
                    result["valid"] = False

        # Check expected output columns (Expected_<output_name>)
        if expected_outputs:
            for out_name in expected_outputs:
                exp_col = f"Expected_{out_name}"
                if exp_col not in headers:
                    sheet_info["errors"].append(f"Missing expected output column: '{exp_col}'.")
                    result["valid"] = False

        # Check data rows for empty cells
        if ws.max_row and ws.max_row < 2:
            sheet_info["errors"].append("Sheet has no data rows (only header).")
            result["valid"] = False
        else:
            empty_cells = []
            for row_idx in range(2, (ws.max_row or 1) + 1):
                for col_idx, header in enumerate(headers, 1):
                    cell_val = ws.cell(row=row_idx, column=col_idx).value
                    if cell_val is None or (isinstance(cell_val, str) and cell_val.strip() == ""):
                        empty_cells.append(f"{header} (row {row_idx})")
            if empty_cells:
                sheet_info["errors"].append(
                    f"{len(empty_cells)} empty cell(s): {', '.join(empty_cells[:5])}"
                    + (f" ... and {len(empty_cells) - 5} more" if len(empty_cells) > 5 else "")
                )
                result["valid"] = False

            # Check that data values are numeric
            non_numeric = []
            for row_idx in range(2, (ws.max_row or 1) + 1):
                for col_idx, header in enumerate(headers, 1):
                    cell_val = ws.cell(row=row_idx, column=col_idx).value
                    if cell_val is not None and not isinstance(cell_val, (int, float)):
                        try:
                            float(cell_val)
                        except (ValueError, TypeError):
                            non_numeric.append(f"{header} (row {row_idx}): '{cell_val}'")
            if non_numeric:
                sheet_info["warnings"].append(
                    f"{len(non_numeric)} non-numeric value(s): {', '.join(non_numeric[:3])}"
                    + (f" ... and {len(non_numeric) - 3} more" if len(non_numeric) > 3 else "")
                )

        result["sheets"].append(sheet_info)

    # Aggregate sheet-level errors
    for si in result["sheets"]:
        result["errors"].extend(si["errors"])
        result["warnings"].extend(si["warnings"])

    return result


@app.post("/api/validate-test-data/{session_id}")
async def validate_test_data(session_id: str):
    """Validate the currently uploaded test data Excel."""
    session_dir = UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")

    xlsx_files = list(session_dir.glob("*_TestData.xlsx"))
    if not xlsx_files:
        xlsx_files = list(session_dir.glob("*.xlsx")) + list(session_dir.glob("*.xls"))
    if not xlsx_files:
        raise HTTPException(404, "No test data Excel found.")

    return _validate_test_data_excel(xlsx_files[0], session_id)


@app.post("/api/run/{session_id}")
async def run_tests(
    session_id: str,
    background_tasks: BackgroundTasks,
    options: Optional[RunOptions] = None,
):
    """
    Kick off the full test automation pipeline (Phases 2-4) as a background job.
    Returns a job_id to poll for status.
    """
    session_dir = UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")

    slx_files = list(session_dir.glob("*.slx"))
    if not slx_files:
        raise HTTPException(400, "No .slx model found")

    # Look for test data Excel (generated template or user-uploaded)
    xlsx_files = list(session_dir.glob("*_TestData.xlsx"))
    if not xlsx_files:
        # Fall back to any xlsx
        xlsx_files = list(session_dir.glob("*.xlsx")) + list(session_dir.glob("*.xls"))
    if not xlsx_files:
        raise HTTPException(
            400,
            "No test data Excel found. Generate a template first via /api/generate-template.",
        )

    job_id = str(uuid.uuid4())[:8]
    output_dir = OUTPUT_DIR / session_id / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow().isoformat()
    job_store[job_id] = {
        "job_id": job_id,
        "session_id": session_id,
        "status": "pending",
        "progress": 0,
        "current_phase": "Queued",
        "message": "Test automation job queued",
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "model_path": str(slx_files[0]),
        "excel_path": str(xlsx_files[0]),
        "output_dir": str(output_dir),
        "options": options.model_dump() if options else {},
    }

    # Run in background to not block the API
    background_tasks.add_task(execute_test_automation, job_id)

    return {"job_id": job_id, "status": "pending", "message": "Job queued"}


async def execute_test_automation(job_id: str):
    """Background task: run the full MATLAB test automation pipeline."""
    job = job_store[job_id]
    loop = asyncio.get_event_loop()

    def update_job(status, progress, phase, message, **kwargs):
        job["status"] = status
        job["progress"] = progress
        job["current_phase"] = phase
        job["message"] = message
        job["updated_at"] = datetime.utcnow().isoformat()
        job.update(kwargs)
        logger.info(f"[Job {job_id}] {phase}: {message} ({progress}%)")

    try:
        update_job("running", 5, "Connecting", "Connecting to MATLAB engine...")
        eng = await loop.run_in_executor(None, get_matlab_engine)

        model_path = job["model_path"]
        excel_path = job["excel_path"]
        output_dir = job["output_dir"]
        opts = job["options"]

        # Build MATLAB options struct
        update_job("running", 10, "Phase 1", "Analyzing model...")

        # We call the test_automation.m function via the engine
        # Build the options struct in MATLAB
        eng.eval("clear automation_options;", nargout=0)
        eng.eval("automation_options = struct();", nargout=0)
        eng.eval(
            f"automation_options.cleanupHarness = {str(opts.get('cleanup_harness', False)).lower()};",
            nargout=0,
        )
        eng.eval(
            f"automation_options.cleanupTestFile = {str(opts.get('cleanup_test_file', False)).lower()};",
            nargout=0,
        )

        stop_time = opts.get("stop_time", "")
        fixed_step = opts.get("fixed_step", "")
        eng.eval(f"automation_options.stopTime = '{stop_time}';", nargout=0)
        eng.eval(f"automation_options.fixedStep = '{fixed_step}';", nargout=0)

        update_job("running", 15, "Phase 1", "Loading model and identifying I/O...")

        # Call the master automation function
        # This is a long-running call, so we wrap it in run_in_executor
        def run_matlab_automation():
            result = eng.test_automation(model_path, excel_path, output_dir, nargout=1)
            return result

        update_job("running", 20, "Phase 2", "Creating test harness...")

        # We need to run this synchronously in MATLAB but asynchronously from Python's POV
        # The MATLAB function handles all phases internally, but we can't get mid-progress.
        # Instead, let's run phase by phase from Python for better progress reporting.

        result = await run_phases_individually(eng, job_id, model_path, excel_path, output_dir, opts, loop)

        update_job("completed", 100, "Done", "Test automation completed successfully", result=result)

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[Job {job_id}] Error: {e}\n{tb}")
        update_job("error", job["progress"], "Error", str(e), error=str(e))


async def run_phases_individually(eng, job_id, model_path, excel_path, output_dir, opts, loop):
    """Run each phase separately from Python for granular progress tracking."""
    job = job_store[job_id]
    result = {"phases": {}}

    model_dir = str(Path(model_path).parent)
    model_name = Path(model_path).stem

    def update_job(status, progress, phase, message, **kwargs):
        job["status"] = status
        job["progress"] = progress
        job["current_phase"] = phase
        job["message"] = message
        job["updated_at"] = datetime.utcnow().isoformat()
        job.update(kwargs)

    # ── Phase 1: Analysis ──
    update_job("running", 15, "Phase 1: Analyze", "Loading model and identifying I/O...")

    def phase1():
        # Remove any other paths that contain a file with the same model name
        # to avoid MATLAB's "shadowed file" warning
        try:
            eng.eval(f"""
            pathList = strsplit(path, pathsep);
            for pi = 1:length(pathList)
                p = pathList{{pi}};
                if exist(fullfile(p, '{model_name}.slx'), 'file') && ~strcmp(p, '{model_dir}')
                    rmpath(p);
                    fprintf('Removed shadowing path: %s\\n', p);
                end
            end
            """, nargout=0)
        except Exception:
            pass

        eng.addpath(model_dir, nargout=0)
        eng.addpath(str(MATLAB_SCRIPTS_DIR), nargout=0)

        # Check licenses
        licenses = {}
        for tb in ["Simulink", "Simulink_Test", "Simulink_Coverage"]:
            licenses[tb] = bool(eng.eval(f"license('test', '{tb}')", nargout=1))

        if not licenses.get("Simulink"):
            raise RuntimeError("Simulink license not available")
        if not licenses.get("Simulink_Test"):
            raise RuntimeError("Simulink Test license not available")

        # Close any previously loaded model with the same name
        try:
            eng.close_system(model_name, 0.0, nargout=0)
            logger.info(f"Closed previously loaded model: {model_name}")
        except Exception:
            pass  # Model wasn't loaded — safe to ignore

        eng.load_system(model_path, nargout=0)

        # Get inputs
        inport_blocks = eng.find_system(model_name, "SearchDepth", 1.0, "BlockType", "Inport", nargout=1)
        inputs = []
        if inport_blocks:
            blocks = inport_blocks if isinstance(inport_blocks, list) else [inport_blocks]
            for block in blocks:
                inputs.append({
                    "name": eng.get_param(block, "Name", nargout=1),
                    "port": eng.get_param(block, "Port", nargout=1),
                    "dataType": eng.get_param(block, "OutDataTypeStr", nargout=1),
                })

        # Get outputs
        outport_blocks = eng.find_system(model_name, "SearchDepth", 1.0, "BlockType", "Outport", nargout=1)
        outputs = []
        if outport_blocks:
            blocks = outport_blocks if isinstance(outport_blocks, list) else [outport_blocks]
            for block in blocks:
                outputs.append({
                    "name": eng.get_param(block, "Name", nargout=1),
                    "port": eng.get_param(block, "Port", nargout=1),
                    "dataType": eng.get_param(block, "OutDataTypeStr", nargout=1),
                })

        stop_time = eng.get_param(model_name, "StopTime", nargout=1)
        fixed_step = eng.get_param(model_name, "FixedStep", nargout=1)
        solver = eng.get_param(model_name, "SolverName", nargout=1)

        return {
            "model_name": model_name,
            "inputs": inputs,
            "outputs": outputs,
            "solver": solver,
            "stop_time": stop_time,
            "fixed_step": fixed_step,
            "licenses": licenses,
        }

    analysis = await loop.run_in_executor(None, phase1)
    result["phases"]["analysis"] = analysis
    result["model_name"] = model_name
    update_job("running", 30, "Phase 1: Analyze", f"Model analyzed: {len(analysis['inputs'])} inputs, {len(analysis['outputs'])} outputs")

    # ── Phase 2: Harness ──
    update_job("running", 35, "Phase 2: Harness", "Creating test harness...")
    harness_name = f"{model_name}_AutoHarness"

    def phase2():
        # Remove existing harness if present
        try:
            eng.eval(f"""
            try
                harnesses = sltest.harness.find('{model_name}');
                for i = 1:length(harnesses)
                    if strcmp(harnesses(i).name, '{harness_name}')
                        sltest.harness.delete('{model_name}', '{harness_name}');
                        break;
                    end
                end
            catch
            end
            """, nargout=0)
        except Exception:
            pass

        # Determine the time step AND max stop time from the Excel data
        time_step_val = opts.get("fixed_step", "")
        excel_stop_time = ""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
            ws = wb[wb.sheetnames[0]]
            all_rows = list(ws.iter_rows(min_row=1, values_only=True))
            wb.close()
            if all_rows and "Time" in [str(h) for h in all_rows[0]]:
                time_idx = [str(h) for h in all_rows[0]].index("Time")
                # Detect time step from first two data rows
                if not time_step_val and len(all_rows) >= 3:
                    if all_rows[1][time_idx] is not None and all_rows[2][time_idx] is not None:
                        time_step_val = str(float(all_rows[2][time_idx]) - float(all_rows[1][time_idx]))
                # Detect max time (last data row's Time value) as stop time
                for row in reversed(all_rows[1:]):
                    if row[time_idx] is not None:
                        excel_stop_time = str(float(row[time_idx]))
                        break
                logger.info(f"Auto-detected from Excel: time_step={time_step_val}, stop_time={excel_stop_time}")
        except Exception as e:
            logger.warning(f"Could not auto-detect time step/stop time from Excel: {e}")

        if not time_step_val:
            time_step_val = "0.1"  # safe default

        # Determine the effective stop time: user opts > Excel detection > model default
        effective_stop_time = opts.get("stop_time", "") or excel_stop_time or analysis.get("stop_time", "10")
        logger.info(f"Effective stop time: {effective_stop_time} (opts={opts.get('stop_time','')}, excel={excel_stop_time}, model={analysis.get('stop_time','')})")

        eng.eval(f"""
        % Enable signal logging on output port lines BEFORE harness creation
        outPorts = find_system('{model_name}', 'SearchDepth', 1, 'BlockType', 'Outport');
        for oIdx = 1:length(outPorts)
            blk = outPorts{{oIdx}};
            ph = get_param(blk, 'PortHandles');
            lineH = get_param(ph.Inport, 'Line');
            if lineH ~= -1
                srcPort = get_param(lineH, 'SrcPortHandle');
                if srcPort ~= -1
                    portName = get_param(blk, 'Name');
                    set_param(srcPort, 'DataLogging', 'on');
                    set_param(srcPort, 'DataLoggingNameMode', 'Custom');
                    set_param(srcPort, 'DataLoggingName', portName);
                    fprintf('Signal logging enabled for: %s\\n', portName);
                end
            end
        end

        % Force fixed-step solver so output time points match input data
        set_param('{model_name}', 'SolverType', 'Fixed-step');
        set_param('{model_name}', 'Solver', 'FixedStepDiscrete');
        set_param('{model_name}', 'FixedStep', '{time_step_val}');
        fprintf('Solver set to Fixed-step (FixedStepDiscrete) with step = {time_step_val}\\n');

        % Set model StopTime to match Excel data (not model default)
        set_param('{model_name}', 'StopTime', '{effective_stop_time}');
        fprintf('Model StopTime set to {effective_stop_time} (matches Excel data)\\n');

        save_system('{model_name}');

        sltest.harness.create('{model_name}', ...
            'Name', '{harness_name}', ...
            'Source', 'Inport', ...
            'Sink', 'Outport', ...
            'VerificationMode', 'Normal', ...
            'LogOutputs', true, ...
            'RebuildOnOpen', true);
        """, nargout=0)
        return {"name": harness_name, "created": True, "effective_stop_time": effective_stop_time, "excel_stop_time": excel_stop_time}

    harness_result = await loop.run_in_executor(None, phase2)
    result["phases"]["harness"] = harness_result
    detected_stop_time = harness_result.get("effective_stop_time", "")
    update_job("running", 50, "Phase 2: Harness", f"Harness '{harness_name}' created (StopTime={detected_stop_time})")

    # ── Phase 3: Test Generation (Simulink Test-compliant Excel approach) ──
    update_job("running", 55, "Phase 3: Test Gen", "Creating test file from Excel template...")

    input_names = [inp["name"] for inp in analysis["inputs"]]
    input_dtypes = [inp.get("dataType", "double") for inp in analysis["inputs"]]
    output_names = [out["name"] for out in analysis["outputs"]]
    # Use the effective stop time: user opts > Excel detection > model default
    sim_stop_time = detected_stop_time or opts.get("stop_time") or analysis["stop_time"]

    def phase3():
        test_file_path = str(Path(output_dir) / f"{model_name}_AutoTest.mldatx")

        # Count the number of sheets (scenarios) in the Excel file
        # Each sheet = one test scenario/iteration
        matlab_code = f"""
        % Count sheets in the Simulink Test-compliant Excel
        sheetNames = cellstr(sheetnames('{excel_path}'));
        numScenarios = length(sheetNames);

        % Clear previous test manager state
        sltest.testmanager.clear();
        sltest.testmanager.clearResults();

        % Create test file
        if exist('{test_file_path}', 'file')
            delete('{test_file_path}');
        end
        tf = sltest.testmanager.TestFile('{test_file_path}');
        ts = tf.getTestSuites();
        if isempty(ts)
            ts = tf.createTestSuite('{model_name}_TestSuite');
        else
            ts = ts(1);
            ts.Name = '{model_name}_TestSuite';
        end

        % Remove any default test cases that were auto-created
        defaultTCs = ts.getTestCases();
        for dci = 1:length(defaultTCs)
            defaultTCs(dci).remove();
        end

        hasSlCov = license('test', 'Simulink_Coverage');

        % Create one test case per Excel sheet (scenario)
        for sc = 1:numScenarios
            sheetName = sheetNames{{sc}};
            tcName = sprintf('{model_name}_TC_%d_%s', sc, sheetName);
            tc = ts.createTestCase('baseline', tcName);
            tc.setProperty('model', '{model_name}');
            tc.setProperty('HarnessName', '{harness_name}', 'HarnessOwner', '{model_name}');
            tc.setProperty('StopTime', str2double('{sim_stop_time}'));
            % The model StopTime was already set in Phase 2 to {sim_stop_time}
            % so [Model Settings] will also use this value

            % Enable coverage
            if hasSlCov
                try
                    covSettings = tc.getCoverageSettings();
                    covSettings.RecordCoverage = true;
                    covSettings.MdlRefCoverage = true;
                    covSettings.MetricSettings = 'dcme';
                catch
                end
            end

            % Read the scenario data from this sheet
            scenarioData = readtable('{excel_path}', 'Sheet', sheetName, 'VariableNamingRule', 'preserve');
            scenarioCols = scenarioData.Properties.VariableNames;

            % Build input Dataset from the time-series data in this sheet
            if ismember('Time', scenarioCols)
                timeVec = scenarioData.Time;
            else
                % If no Time column, create a default time vector
                timeVec = linspace(0, str2double('{sim_stop_time}'), height(scenarioData))';
            end

            inputDS = Simulink.SimulationData.Dataset;
            inputNames = {{{', '.join(f"'{n}'" for n in input_names)}}};
            inputDTypes = {{{', '.join(f"'{d}'" for d in input_dtypes)}}};
            outputNames = {{{', '.join(f"'{n}'" for n in output_names)}}};

            for inp = 1:length(inputNames)
                inpName = inputNames{{inp}};
                if ismember(inpName, scenarioCols)
                    vals = scenarioData.(inpName);
                    if iscell(vals)
                        vals = cellfun(@(x) str2double(string(x)), vals);
                    end
                    % Cast to the data type expected by the inport
                    inpDType = inputDTypes{{inp}};
                    switch inpDType
                        case 'single'
                            vals = single(vals);
                        case 'int8'
                            vals = int8(vals);
                        case 'uint8'
                            vals = uint8(vals);
                        case 'int16'
                            vals = int16(vals);
                        case 'uint16'
                            vals = uint16(vals);
                        case 'int32'
                            vals = int32(vals);
                        case 'uint32'
                            vals = uint32(vals);
                        case 'boolean'
                            vals = logical(vals);
                        otherwise
                            vals = double(vals);
                    end
                    sig = timeseries(vals, double(timeVec));
                    sig.Name = inpName;
                    inputDS = inputDS.addElement(sig);
                end
            end

            % Read expected output columns (Expected_<name>) for pass/fail comparison
            % Store ALL time-step values (not just last) for per-row reporting
            if ~exist('expectedOutputs', 'var')
                expectedOutputs = cell(numScenarios, length(outputNames));
            end
            if ~exist('expectedOutputsAll', 'var')
                expectedOutputsAll = cell(numScenarios, length(outputNames));
            end
            for oi = 1:length(outputNames)
                expColName = ['Expected_' outputNames{{oi}}];
                if ismember(expColName, scenarioCols)
                    vals = scenarioData.(expColName);
                    if iscell(vals)
                        vals = cellfun(@(x) str2double(string(x)), vals);
                    end
                    expectedOutputs{{sc, oi}} = double(vals(end));
                    expectedOutputsAll{{sc, oi}} = double(vals(:));
                else
                    expectedOutputs{{sc, oi}} = NaN;
                    expectedOutputsAll{{sc, oi}} = NaN;
                end
            end

            % Store ALL time-step values for inputs
            if ~exist('inputValuesSummary', 'var')
                inputValuesSummary = cell(numScenarios, length(inputNames));
            end
            if ~exist('inputValuesAll', 'var')
                inputValuesAll = cell(numScenarios, length(inputNames));
            end
            if ~exist('timeVecsAll', 'var')
                timeVecsAll = cell(numScenarios, 1);
            end
            timeVecsAll{{sc}} = double(timeVec(:));
            for ini = 1:length(inputNames)
                inpName = inputNames{{ini}};
                if ismember(inpName, scenarioCols)
                    vals = scenarioData.(inpName);
                    if iscell(vals)
                        vals = cellfun(@(x) str2double(string(x)), vals);
                    end
                    inputValuesSummary{{sc, ini}} = double(vals(end));
                    inputValuesAll{{sc, ini}} = double(vals(:));
                else
                    inputValuesSummary{{sc, ini}} = NaN;
                    inputValuesAll{{sc, ini}} = NaN;
                end
            end

            % Save input Dataset to a MAT file and add as external input
            matFilePath = fullfile('{output_dir}', sprintf('input_scenario_%d.mat', sc));
            inputData = inputDS; %#ok<NASGU>
            save(matFilePath, 'inputData');
            testInput = tc.addInput(matFilePath);
            % Map the input signals to model inports by block name
            map(testInput, 'Mode', 0);
            fprintf('  Scenario %d: Input mapped (MappingStatus=%s)\\n', sc, testInput.MappingStatus);

            % --- Add baseline criteria by creating a baseline MAT file directly ---
            try
                % Build a baseline Dataset from expected output values
                baselineDS = Simulink.SimulationData.Dataset;
                baselineDS.Name = 'baselineData';
                hasExpected = false;

                for oi = 1:length(outputNames)
                    expColName = ['Expected_' outputNames{{oi}}];
                    if ismember(expColName, scenarioCols)
                        expVals = scenarioData.(expColName);
                        if iscell(expVals)
                            expVals = cellfun(@(x) str2double(string(x)), expVals);
                        end
                        bSig = timeseries(double(expVals), double(timeVec));
                        bSig.Name = outputNames{{oi}};
                        baselineDS = baselineDS.addElement(bSig);
                        hasExpected = true;
                    end
                end

                if hasExpected
                    % Save the baseline Dataset to a MAT file
                    baselineMatPath = fullfile('{output_dir}', sprintf('baseline_scenario_%d.mat', sc));
                    baselineData = baselineDS; %#ok<NASGU>
                    save(baselineMatPath, 'baselineData');

                    % Add baseline criteria to the test case
                    bc = tc.addBaselineCriteria(baselineMatPath);
                    fprintf('  Scenario %d: Baseline criteria added from expected values\\n', sc);
                end
            catch bcErr
                fprintf('  Scenario %d: Baseline criteria warning: %s\\n', sc, bcErr.message);
            end
        end

        tf.saveToFile();
        automation_numScenarios = numScenarios;
        """

        eng.eval(matlab_code, nargout=0)
        num_scenarios = int(eng.workspace["automation_numScenarios"])

        return {
            "test_file_path": test_file_path,
            "num_test_cases": num_scenarios,
            "input_names": input_names,
            "output_names": output_names,
        }

    testgen_result = await loop.run_in_executor(None, phase3)
    result["phases"]["testgen"] = testgen_result
    update_job("running", 65, "Phase 3: Test Gen", f"{testgen_result['num_test_cases']} test cases created from Excel scenarios")

    # ── Phase 4: Execution ──
    update_job("running", 70, "Phase 4: Execute", "Running test suite (this may take a while)...")

    def phase4():
        test_file_path = testgen_result["test_file_path"]

        matlab_code = f"""
        % Reload test file and run via test suite
        tf = sltest.testmanager.TestFile('{test_file_path}');
        ts = tf.getTestSuites();
        ts = ts(1);
        numScenarios = automation_numScenarios;
        inputNames = {{{', '.join(f"'{n}'" for n in input_names)}}};
        outputNames = {{{', '.join(f"'{n}'" for n in output_names)}}};

        resultSet = ts.run();

        % Parse results
        tsResults = resultSet.getTestSuiteResults();
        automation_results = struct();
        automation_results.overallOutcome = 'Unknown';
        automation_results.testCases = {{}};

        % Storage for actual output values (last time step summary + all time steps)
        actualOutputs = cell(numScenarios, length(outputNames));
        actualOutputsAll = cell(numScenarios, length(outputNames));
        actualTimeAll = cell(numScenarios, 1);

        % --- Hybrid approach: run sim() per scenario to extract actual outputs ---
        fprintf('Extracting actual outputs via sim()...\\n');
        for sc = 1:numScenarios
            matFilePath = fullfile('{output_dir}', sprintf('input_scenario_%d.mat', sc));
            if ~exist(matFilePath, 'file')
                fprintf('  Scenario %d: MAT file not found, skipping\\n', sc);
                continue;
            end
            try
                loaded = load(matFilePath, 'inputData');
                simIn = Simulink.SimulationInput('{model_name}');
                simIn = simIn.setExternalInput(loaded.inputData);
                simOut = sim(simIn);

                % Determine the stop time for this scenario to match output at correct time
                scenarioStopTime = str2double('{sim_stop_time}');

                % Try logsout first (has named signals)
                gotOutput = false;
                try
                    logsout = simOut.get('logsout');
                    if ~isempty(logsout) && isa(logsout, 'Simulink.SimulationData.Dataset')
                        for oi = 1:length(outputNames)
                            outName = outputNames{{oi}};
                            for ei = 1:logsout.numElements
                                elem = logsout.getElement(ei);
                                if strcmp(elem.Name, outName)
                                    sigTime = elem.Values.Time;
                                    sigData = double(elem.Values.Data);
                                    % Store ALL time-step values
                                    actualOutputsAll{{sc, oi}} = sigData(:);
                                    actualTimeAll{{sc}} = sigTime(:);
                                    % Also store last/stop-time value for summary
                                    [~, tidx] = min(abs(sigTime - scenarioStopTime));
                                    actualOutputs{{sc, oi}} = sigData(tidx);
                                    gotOutput = true;
                                    break;
                                end
                            end
                        end
                    end
                catch, end

                % Fallback: yout (indexed by output port order)
                if ~gotOutput
                    try
                        yout = simOut.get('yout');
                        if ~isempty(yout) && isa(yout, 'Simulink.SimulationData.Dataset')
                            for oi = 1:min(length(outputNames), yout.numElements)
                                elem = yout.getElement(oi);
                                sigTime = elem.Values.Time;
                                sigData = double(elem.Values.Data);
                                actualOutputsAll{{sc, oi}} = sigData(:);
                                actualTimeAll{{sc}} = sigTime(:);
                                [~, tidx] = min(abs(sigTime - scenarioStopTime));
                                actualOutputs{{sc, oi}} = sigData(tidx);
                            end
                        end
                    catch, end
                end

                fprintf('  Scenario %d:', sc);
                for oi = 1:length(outputNames)
                    val = actualOutputs{{sc, oi}};
                    if isempty(val), val = NaN; end
                    fprintf(' %s=%g', outputNames{{oi}}, val);
                end
                fprintf('\\n');
            catch simErr
                fprintf('  Scenario %d: sim() error: %s\\n', sc, simErr.message);
            end
        end

        allPassed = true;
        caseIdx = 0;

        for tsi = 1:length(tsResults)
            tcResults = tsResults(tsi).getTestCaseResults();
            for tci = 1:length(tcResults)
                caseIdx = caseIdx + 1;
                tcr = tcResults(tci);
                caseRes = struct();
                caseRes.name = char(tcr.Name);

                % Compare actual vs expected to determine pass/fail
                % Check ALL time steps (not just last value)
                caseRes.expectedOutputs = struct();
                caseRes.actualOutputs = struct();
                caseRes.outputMatch = true;
                caseRes.failedSteps = 0;
                caseRes.totalSteps = 0;
                for oi = 1:length(outputNames)
                    outName = outputNames{{oi}};
                    expVal = NaN;
                    if exist('expectedOutputs', 'var') && caseIdx <= size(expectedOutputs, 1)
                        expVal = expectedOutputs{{caseIdx, oi}};
                        if isempty(expVal), expVal = NaN; end
                    end
                    actVal = NaN;
                    if caseIdx <= size(actualOutputs, 1)
                        actVal = actualOutputs{{caseIdx, oi}};
                        if isempty(actVal), actVal = NaN; end
                    end
                    caseRes.expectedOutputs.(outName) = expVal;
                    caseRes.actualOutputs.(outName) = actVal;

                    % Check ALL time steps for this output
                    if exist('expectedOutputsAll', 'var') && caseIdx <= size(expectedOutputsAll, 1) ...
                            && caseIdx <= size(actualOutputsAll, 1)
                        allExp = expectedOutputsAll{{caseIdx, oi}};
                        allAct = actualOutputsAll{{caseIdx, oi}};
                        if ~isempty(allExp) && isnumeric(allExp) && ~isempty(allAct) && isnumeric(allAct)
                            nSteps = min(length(allExp), length(allAct));
                            caseRes.totalSteps = max(caseRes.totalSteps, nSteps);
                            for si = 1:nSteps
                                if ~isnan(allExp(si)) && ~isnan(allAct(si))
                                    if abs(allAct(si) - allExp(si)) > 1e-6
                                        caseRes.outputMatch = false;
                                        caseRes.failedSteps = caseRes.failedSteps + 1;
                                    end
                                end
                            end
                        end
                    else
                        % Fallback: just compare last values
                        if ~isnan(expVal) && ~isnan(actVal)
                            if abs(actVal - expVal) > 1e-6
                                caseRes.outputMatch = false;
                            end
                        end
                    end
                end

                % Final outcome: must pass Simulink test AND match expected outputs
                simOutcome = char(string(tcr.Outcome));
                if caseRes.outputMatch && strcmp(simOutcome, 'Passed')
                    caseRes.outcome = 'Passed';
                elseif strcmp(simOutcome, 'Disabled')
                    caseRes.outcome = 'Disabled';
                else
                    caseRes.outcome = 'Failed';
                    allPassed = false;
                end
                caseRes.simulinkOutcome = simOutcome;

                % Store input values summary
                caseRes.inputValues = struct();
                for ini = 1:length(inputNames)
                    inpName = inputNames{{ini}};
                    inpVal = NaN;
                    if exist('inputValuesSummary', 'var') && caseIdx <= size(inputValuesSummary, 1)
                        inpVal = inputValuesSummary{{caseIdx, ini}};
                        if isempty(inpVal), inpVal = NaN; end
                    end
                    caseRes.inputValues.(inpName) = inpVal;
                end

                % Build per-time-step details for expandable row view
                caseRes.timeSteps = {{}};
                if exist('timeVecsAll', 'var') && caseIdx <= length(timeVecsAll) && ~isempty(timeVecsAll{{caseIdx}})
                    tVec = timeVecsAll{{caseIdx}};
                    numSteps = length(tVec);
                    for ti = 1:numSteps
                        stepRow = struct();
                        stepRow.time = tVec(ti);
                        stepRow.inputs = struct();
                        for ini = 1:length(inputNames)
                            inpName = inputNames{{ini}};
                            if exist('inputValuesAll', 'var') && caseIdx <= size(inputValuesAll, 1)
                                allVals = inputValuesAll{{caseIdx, ini}};
                                if ~isempty(allVals) && ti <= length(allVals)
                                    stepRow.inputs.(inpName) = allVals(ti);
                                else
                                    stepRow.inputs.(inpName) = NaN;
                                end
                            else
                                stepRow.inputs.(inpName) = NaN;
                            end
                        end
                        stepRow.expected = struct();
                        stepRow.actual = struct();
                        stepRow.rowMatch = true;
                        for oi = 1:length(outputNames)
                            outName = outputNames{{oi}};
                            % Expected value at this time step
                            expV = NaN;
                            if exist('expectedOutputsAll', 'var') && caseIdx <= size(expectedOutputsAll, 1)
                                allExp = expectedOutputsAll{{caseIdx, oi}};
                                if ~isempty(allExp) && isnumeric(allExp) && ti <= length(allExp)
                                    expV = allExp(ti);
                                end
                            end
                            % Actual value at this time step
                            actV = NaN;
                            if caseIdx <= size(actualOutputsAll, 1)
                                allAct = actualOutputsAll{{caseIdx, oi}};
                                if ~isempty(allAct) && isnumeric(allAct) && ti <= length(allAct)
                                    actV = allAct(ti);
                                end
                            end
                            stepRow.expected.(outName) = expV;
                            stepRow.actual.(outName) = actV;
                            if ~isnan(expV) && ~isnan(actV) && abs(actV - expV) > 1e-6
                                stepRow.rowMatch = false;
                            end
                        end
                        caseRes.timeSteps{{ti}} = stepRow;
                    end
                end

                automation_results.testCases{{caseIdx}} = caseRes;
            end
        end

        if allPassed
            automation_results.overallOutcome = 'Passed';
        else
            automation_results.overallOutcome = 'Failed';
        end

        % Export coverage report
        automation_results.coverageAvailable = false;
        automation_results.coverageReportPath = '';
        if license('test', 'Simulink_Coverage')
            try
                covReportDir = fullfile('{output_dir}', 'coverage_report');
                if ~exist(covReportDir, 'dir'), mkdir(covReportDir); end
                covGenerated = false;
                for tsi = 1:length(tsResults)
                    tcResults = tsResults(tsi).getTestCaseResults();
                    for tci = 1:length(tcResults)
                        try
                            covResult = tcResults(tci).getCoverageResults();
                            if ~isempty(covResult)
                                reportPath = fullfile(covReportDir, 'coverage_report.html');
                                cvhtml(reportPath, covResult);
                                automation_results.coverageAvailable = true;
                                automation_results.coverageReportPath = reportPath;
                                covGenerated = true;
                                break;
                            end
                        catch
                        end
                    end
                    if covGenerated, break; end
                end
            catch covErr
                automation_results.coverageError = covErr.message;
            end
        end

        automation_results_json = jsonencode(automation_results);
        """

        eng.eval(matlab_code, nargout=0)
        results_json = eng.workspace["automation_results_json"]
        return json.loads(results_json)

    execution_result = await loop.run_in_executor(None, phase4)
    result["phases"]["execution"] = execution_result
    update_job("running", 85, "Phase 4: Execute", f"Tests completed: {execution_result.get('overallOutcome', 'Unknown')}")

    # ── Phase 5: Export Results to Excel ──
    update_job("running", 90, "Phase 5: Export", "Writing results to Excel...")

    def phase5():
        output_excel = str(Path(output_dir) / f"{model_name}_TestResults.xlsx")

        # Build Excel export command — generate a comprehensive results report
        input_col_names = ', '.join(f"'{n}'" for n in input_names)
        output_col_names = ', '.join(f"'{n}'" for n in output_names)

        matlab_code = f"""
        % Read the test data Excel to get scenario info
        sheetNames = cellstr(sheetnames('{excel_path}'));
        numScenarios = length(sheetNames);
        inputNames = {{{input_col_names}}};
        outputNames = {{{output_col_names}}};
        numCases = length(automation_results.testCases);

        % Build comprehensive results with ALL time steps per scenario
        % Summary sheet: one row per test case (last-step values)
        tcNameCol     = cell(numCases, 1);
        scenarioCol   = cell(numCases, 1);
        statusCol     = cell(numCases, 1);
        simOutcomeCol = cell(numCases, 1);
        inputCols  = nan(numCases, length(inputNames));
        expectedCols = nan(numCases, length(outputNames));
        actualCols = nan(numCases, length(outputNames));

        for i = 1:numCases
            tc = automation_results.testCases{{i}};
            tcNameCol{{i}} = tc.name;
            if i <= numScenarios
                scenarioCol{{i}} = sheetNames{{i}};
            else
                scenarioCol{{i}} = 'N/A';
            end
            statusCol{{i}} = tc.outcome;
            simOutcomeCol{{i}} = tc.simulinkOutcome;

            for ini = 1:length(inputNames)
                try, inputCols(i, ini) = tc.inputValues.(inputNames{{ini}}); catch, end
            end
            for oi = 1:length(outputNames)
                try, expectedCols(i, oi) = tc.expectedOutputs.(outputNames{{oi}}); catch, end
            end
            for oi = 1:length(outputNames)
                try, actualCols(i, oi) = tc.actualOutputs.(outputNames{{oi}}); catch, end
            end
        end

        % Summary sheet
        resultsT = table(tcNameCol, scenarioCol, 'VariableNames', {{'TestCase', 'Scenario'}});
        for ini = 1:length(inputNames)
            resultsT.(inputNames{{ini}}) = inputCols(:, ini);
        end
        for oi = 1:length(outputNames)
            resultsT.(['Expected_' outputNames{{oi}}]) = expectedCols(:, oi);
        end
        for oi = 1:length(outputNames)
            resultsT.(['Actual_' outputNames{{oi}}]) = actualCols(:, oi);
        end
        resultsT.SimulinkOutcome = simOutcomeCol;
        resultsT.Status = statusCol;
        writetable(resultsT, '{output_excel}', 'Sheet', 'Summary');

        % Detailed sheet: all time steps for all scenarios
        allRows = {{}};
        rowIdx = 0;
        for i = 1:numCases
            tc = automation_results.testCases{{i}};
            if isfield(tc, 'timeSteps') && ~isempty(tc.timeSteps)
                nSteps = length(tc.timeSteps);
                for ti = 1:nSteps
                    rowIdx = rowIdx + 1;
                    step = tc.timeSteps{{ti}};
                    allRows{{rowIdx, 1}} = tc.name;
                    if i <= numScenarios
                        allRows{{rowIdx, 2}} = sheetNames{{i}};
                    else
                        allRows{{rowIdx, 2}} = 'N/A';
                    end
                    allRows{{rowIdx, 3}} = step.time;
                    colOffset = 3;
                    for ini = 1:length(inputNames)
                        try
                            allRows{{rowIdx, colOffset + ini}} = step.inputs.(inputNames{{ini}});
                        catch
                            allRows{{rowIdx, colOffset + ini}} = NaN;
                        end
                    end
                    colOffset = colOffset + length(inputNames);
                    for oi = 1:length(outputNames)
                        try
                            allRows{{rowIdx, colOffset + oi}} = step.expected.(outputNames{{oi}});
                        catch
                            allRows{{rowIdx, colOffset + oi}} = NaN;
                        end
                    end
                    colOffset = colOffset + length(outputNames);
                    for oi = 1:length(outputNames)
                        try
                            allRows{{rowIdx, colOffset + oi}} = step.actual.(outputNames{{oi}});
                        catch
                            allRows{{rowIdx, colOffset + oi}} = NaN;
                        end
                    end
                    colOffset = colOffset + length(outputNames);
                    if step.rowMatch
                        allRows{{rowIdx, colOffset + 1}} = 'Passed';
                    else
                        allRows{{rowIdx, colOffset + 1}} = 'Failed';
                    end
                end
            end
        end

        if rowIdx > 0
            % Build headers
            headers = {{'TestCase', 'Scenario', 'Time'}};
            for ini = 1:length(inputNames)
                headers{{end+1}} = inputNames{{ini}};
            end
            for oi = 1:length(outputNames)
                headers{{end+1}} = ['Expected_' outputNames{{oi}}];
            end
            for oi = 1:length(outputNames)
                headers{{end+1}} = ['Actual_' outputNames{{oi}}];
            end
            headers{{end+1}} = 'RowStatus';

            detailT = cell2table(allRows, 'VariableNames', headers);
            writetable(detailT, '{output_excel}', 'Sheet', 'DetailedResults');
        end
        """

        eng.eval(matlab_code, nargout=0)
        return {"excel_path": output_excel}

    export_result = await loop.run_in_executor(None, phase5)
    result["phases"]["export"] = export_result

    # ── Cleanup ──
    if opts.get("cleanup_harness", False):
        try:
            def cleanup_harness():
                eng.eval(f"sltest.harness.delete('{model_name}', '{harness_name}');", nargout=0)
            await loop.run_in_executor(None, cleanup_harness)
        except Exception:
            pass

    if opts.get("cleanup_test_file", False):
        try:
            test_fp = testgen_result["test_file_path"]
            if os.path.exists(test_fp):
                os.remove(test_fp)
        except Exception:
            pass

    # Clean up MAT input files (not needed after test execution)

    return result


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Poll job status."""
    if job_id not in job_store:
        raise HTTPException(404, f"Job {job_id} not found")

    job = job_store[job_id]
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "progress": job["progress"],
        "current_phase": job["current_phase"],
        "message": job["message"],
        "result": job.get("result"),
        "error": job.get("error"),
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }


@app.get("/api/download/excel/{session_id}/{job_id}")
async def download_excel(session_id: str, job_id: str):
    """Download the results Excel file."""
    output_dir = OUTPUT_DIR / session_id / job_id
    excel_files = list(output_dir.glob("*_TestResults.xlsx"))
    if not excel_files:
        raise HTTPException(404, "Results Excel file not found")
    return FileResponse(
        excel_files[0],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=excel_files[0].name,
    )


@app.get("/api/download/coverage/{session_id}/{job_id}")
async def download_coverage(session_id: str, job_id: str):
    """Download the coverage report (HTML)."""
    cov_dir = OUTPUT_DIR / session_id / job_id / "coverage_report"
    if not cov_dir.exists():
        raise HTTPException(404, "Coverage report not found")

    # Zip the coverage report directory
    zip_path = OUTPUT_DIR / session_id / job_id / "coverage_report.zip"
    if not zip_path.exists():
        shutil.make_archive(str(zip_path).replace(".zip", ""), "zip", str(cov_dir))

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="coverage_report.zip",
    )


@app.get("/api/download/test-file/{session_id}/{job_id}")
async def download_test_file(session_id: str, job_id: str):
    """Download the generated .mldatx test file."""
    output_dir = OUTPUT_DIR / session_id / job_id
    mldatx_files = list(output_dir.glob("*.mldatx"))
    if not mldatx_files:
        raise HTTPException(404, "Test file not found")
    return FileResponse(
        mldatx_files[0],
        media_type="application/octet-stream",
        filename=mldatx_files[0].name,
    )


@app.delete("/api/session/{session_id}")
async def cleanup_session(session_id: str):
    """Clean up all files for a session."""
    session_dir = UPLOAD_DIR / session_id
    output_dir = OUTPUT_DIR / session_id

    removed = []
    for d in [session_dir, output_dir]:
        if d.exists():
            shutil.rmtree(d)
            removed.append(str(d))

    return {"message": "Session cleaned up", "removed": removed}


@app.post("/api/restart-session/{session_id}")
async def restart_session(session_id: str):
    """
    Restart a session: keeps the uploaded model and analysis but clears
    test data, templates, outputs, and job state so the user can go back
    to the Test Data step with new parameters.
    """
    session_dir = UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(404, f"Session {session_id} not found")

    removed = []

    # Remove generated template Excel
    for f in session_dir.glob("*_TestData.xlsx"):
        f.unlink()
        removed.append(f.name)

    # Remove uploaded test data Excel (user-filled)
    for f in session_dir.glob("*_TestData_filled*"):
        f.unlink()
        removed.append(f.name)
    # Also remove any non-template xlsx that might be test data
    for f in session_dir.glob("*.xlsx"):
        if not f.name.endswith(".slx"):
            f.unlink()
            removed.append(f.name)

    # Remove _test_data_path marker
    marker = session_dir / "_test_data_path"
    if marker.exists():
        marker.unlink()
        removed.append("_test_data_path")

    # Remove outputs for this session
    output_session_dir = OUTPUT_DIR / session_id
    if output_session_dir.exists():
        shutil.rmtree(output_session_dir)
        removed.append(f"outputs/{session_id}")

    # Clear any jobs for this session from job_store
    jobs_cleared = 0
    for jid in list(job_store.keys()):
        job = job_store[jid]
        if job.get("session_id") == session_id:
            del job_store[jid]
            jobs_cleared += 1

    logger.info(f"Session {session_id} restarted: removed {removed}, cleared {jobs_cleared} jobs")
    return {
        "message": "Session restarted — ready for new test data",
        "session_id": session_id,
        "removed": removed,
        "jobs_cleared": jobs_cleared,
    }


@app.post("/api/clear-all")
async def clear_all():
    """Clear all jobs and session data — useful for fresh GUI testing."""
    global job_store
    cleared_jobs = len(job_store)
    job_store = {}

    cleared_sessions = 0
    for d in [UPLOAD_DIR, OUTPUT_DIR]:
        if d.exists():
            for child in d.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                    cleared_sessions += 1

    logger.info(f"Cleared all: {cleared_jobs} jobs, {cleared_sessions} session dirs")
    return {
        "message": "All jobs and sessions cleared",
        "cleared_jobs": cleared_jobs,
        "cleared_sessions": cleared_sessions,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
