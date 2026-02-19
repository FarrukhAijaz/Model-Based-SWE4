"""
Shared utilities and configuration for Synapse Test Manager
"""

import logging
from pathlib import Path
from typing import Dict, Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
MATLAB_SCRIPTS_DIR = BASE_DIR / "matlab_scripts"

# Known sample model in the workspace root
SAMPLE_MODEL = WORKSPACE_DIR / "SimulinkSample.slx"

# Create directories if they don't exist
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("synapse_test_manager")

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
        logger.error(
            "Failed to import matlab.engine. "
            "Please install MATLAB Engine API for Python."
        )
        raise
    except Exception as err:
        logger.error(f"Failed to connect to MATLAB: {err}")
        raise


def check_matlab_licenses(eng) -> dict:
    """Check which required licenses are available."""
    licenses_to_check = [
        "Simulink",
        "Simulink_Test",
        "Simulink_Coverage",
    ]
    result = {}
    for lic in licenses_to_check:
        try:
            out = eng.license("checkout", lic, nargout=1)
            eng.license("checkin", lic, nargout=0)
            result[lic] = True
        except Exception:
            result[lic] = False
    return result


def matlab_struct_to_dict(eng, matlab_var_name: str) -> dict:
    """
    Convert MATLAB struct variable to a Python dict.
    Assumes the struct exists in the base workspace.
    """
    try:
        # Get field names
        field_names = eng.fieldnames(matlab_var_name, nargout=1)
        field_names = [str(f) for f in field_names]

        # Build dict
        result = {}
        for field in field_names:
            val = eng.eval(f"{matlab_var_name}.{field}", nargout=1)

            # Try to convert MATLAB arrays to Python
            try:
                if hasattr(val, "tolist"):
                    val = val.tolist()
                elif hasattr(val, "__iter__") and not isinstance(val, str):
                    val = list(val)
            except Exception:
                pass

            result[field] = val

        return result
    except Exception as e:
        logger.error(f"Error converting MATLAB struct to dict: {e}")
        return {}
