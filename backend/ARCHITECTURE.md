# Synapse Test Manager - Modular Backend Architecture

## Overview

The backend has been refactored into a modular architecture to support multiple testing modules:
- **Model-Based SWE4** (Active) - Simulink model testing via MATLAB
- **Code-Based SWE4** (In Development) - C/C++ code testing

## Architecture

### Module Files

#### `main.py` (Orchestrator)
- **Purpose**: FastAPI application entry point that orchestrates all modules
- **Responsibilities**:
  - Initialize FastAPI app
  - Load and include routers from all modules
  - Manage global lifespan (startup/shutdown)
  - Provide health checks with module status
  - Handle CORS and middleware setup
  - **Error Handling**: Graceful degradation if one module fails

#### `code_based.py` (Code-Based SWE4 Router)
- **Purpose**: APIRouter for C/C++ code testing features
- **Status**: Under development (returns placeholders)
- **Routes**: 
  - `/api/code-based/health` - Health check
  - `/api/code-based/upload` - Code upload
  - `/api/code-based/analyze/{session_id}` - Code analysis
  - `/api/code-based/generate-tests/{session_id}` - Test generation
  - `/api/code-based/run/{session_id}` - Test execution
  - `/api/code-based/job/{job_id}` - Job status

#### `utils.py` (Shared Utilities)
- **Purpose**: Shared configuration, utilities, and helpers
- **Exports**:
  - `BASE_DIR`, `UPLOAD_DIR`, `OUTPUT_DIR` - Directory paths
  - `get_matlab_engine()` - MATLAB connection management
  - `check_matlab_licenses()` - License validation
  - `matlab_struct_to_dict()` - Type conversion utilities

#### `model_based_routes.py` (Reference)
- **Purpose**: Copy of complete Model-Based routes for reference
- **Use**: Can be modified independently to create true APIRouter version

## Failure Isolation

| Scenario | Model-Based | Code-Based | Server |
|----------|-------------|-----------|--------|
| Model-Based fails | ❌ | ✅ | ✅ Degraded |
| Code-Based fails | ✅ | ❌ | ✅ Degraded |
| Both fail | ❌ | ❌ | ✅ Responsive |
| Both work | ✅ | ✅ | ✅ Optimal |

## Module Status

The health check endpoint (`/api/health`) now returns module status:

```json
{
  "status": "ok",
  "modules": {
    "model_based": "ok",
    "code_based": "available"
  },
  ...
}
```

## Adding a New Module

To add a new testing module (e.g., Python testing):

1. **Create `python_based.py`**:
   ```python
   from fastapi import APIRouter
   
   router = APIRouter(
       prefix="/api/python-based",
       tags=["Python Based SWE4"],
   )
   
   @router.get("/health")
   async def health():
       return {"status": "ok"}
   ```

2. **Import in `main.py`**:
   ```python
   try:
       from python_based import router as python_based_router
       PYTHON_BASED_AVAILABLE = True
   except Exception as e:
       PYTHON_BASED_AVAILABLE = False
   ```

3. **Include in app**:
   ```python
   if PYTHON_BASED_AVAILABLE:
       app.include_router(python_based_router)
   ```

4. **Update health check** to include module status

## File Organization

```
backend/
├── main.py                  # FastAPI orchestrator
├── code_based.py            # Code-based SWE4 module (Router)
├── utils.py                 # Shared utilities & config
├── main_original.py         # Backup of original main.py
├── model_based_routes.py    # Reference copy
├── matlab_scripts/          # MATLAB helper scripts
├── uploads/                 # Uploaded session data
├── outputs/                 # Job results/outputs
└── requirements.txt         # Dependencies
```

## Integration with Frontend

The frontend remains unchanged and continues to work with all endpoints:
- `http://localhost:8000/api/health` - Get server & module status
- `http://localhost:8000/api/upload` - Model-Based operations
- `http://localhost:8000/api/code-based/*` - Code-Based operations (when ready)

## Backward Compatibility

✅ All existing Model-Based SWE4 endpoints remain unchanged
✅ Frontend can detect available modules via `/api/health`
✅ Code-Based endpoints return "Coming Soon" responses
✅ If Code-Based module fails, Model-Based remains operational

## Future Development

When ready to implement Code-Based SWE4:
1. Replace placeholder routes in `code_based.py` with real implementation
2. Add necessary dependencies to `requirements.txt`
3. No changes needed to `main.py` - it will automatically include the module

## Debugging

**To check which modules loaded**:
```bash
curl http://localhost:8000/api/health | jq .modules
```

**Backend logs**:
```
✓ Code-Based SWE4 router included
✓ Model-Based SWE4 module initialized
✓ Code-Based SWE4 module initialized
✓ All available modules loaded. Server ready.
```

---

**Version**: 1.0.0  
**Architecture**: Multi-Module with Graceful Degradation  
**Status**: Model-Based ✅ | Code-Based 🚀 (Coming Soon)
