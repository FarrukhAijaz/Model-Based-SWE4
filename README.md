# Simulink Test Automation

A full-stack web application that automates Simulink Unit Testing via the MATLAB Engine API for Python.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                React Frontend (port 3000)            │
│  Upload → Analyze → Execute → Report                │
└────────────────────┬────────────────────────────────┘
                     │ REST API
┌────────────────────▼────────────────────────────────┐
│            FastAPI Backend (port 8000)               │
│  /api/upload  /api/analyze  /api/run  /api/download  │
└────────────────────┬────────────────────────────────┘
                     │ MATLAB Engine API
┌────────────────────▼────────────────────────────────┐
│              MATLAB (Shared Session)                 │
│  Simulink · Simulink Test · Simulink Coverage        │
│  test_automation.m helper script                     │
└──────────────────────────────────────────────────────┘
```

## Prerequisites

- **MATLAB R2023a+** with:
  - Simulink
  - Simulink Test
  - Simulink Coverage (optional, for coverage reports)
- **MATLAB Engine API for Python** installed:
  ```bash
  cd <MATLAB_ROOT>/extern/engines/python
  python setup.py install
  ```
- **Python 3.9+**
- **Node.js 18+** and npm

## Setup

### 1. Share your MATLAB session

Open MATLAB and run:
```matlab
matlab.engine.shareEngine
```

### 2. Start the Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```
The API will be available at `http://localhost:8000`.

### 3. Start the Frontend

```bash
cd frontend
npm install
npm start
```
The UI will open at `http://localhost:3000`.

## How to Use

### Step 1: Upload
- Upload your `.slx` Simulink model file
- Upload your `.xlsx` test data file

### Step 2: Analyze
- The system opens the model and identifies all root-level Inports/Outports
- Solver settings and license availability are displayed

### Step 3: Execute
- Configure options (cleanup, override stop time, etc.)
- The system runs through:
  - **Harness Creation**: `sltest.harness.create` with Inport source / Outport sink
  - **Test File Generation**: Creates `.mldatx` with one test case per Excel row
  - **Test Execution**: `sltest.testmanager.run` with Decision/Condition/MCDC coverage
  - **Results Export**: Updates Excel with per-test-case result sheets

### Step 4: Report
- View pass/fail summary
- Download:
  - Updated Excel with results
  - Coverage report (HTML)
  - Generated `.mldatx` test file

## Excel Test Data Format

The Excel file should have columns matching model Inport names, plus optional `Expected_<Outport>` columns:

| Throttle | Pedal | Expected_Speed | Expected_Status |
|----------|-------|----------------|-----------------|
| 50       | 30    | 45.5           | 1               |
| 100      | 80    | 90.2           | 2               |
| 0        | 0     | 0              | 0               |

- **Input columns**: Must match model Inport block names exactly (case-sensitive)
- **Expected output columns**: Prefix with `Expected_` + Outport block name
- Each row becomes a separate test case

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Check MATLAB connectivity & licenses |
| `/api/upload` | POST | Upload .slx and .xlsx files |
| `/api/analyze/{session_id}` | POST | Analyze model I/O |
| `/api/run/{session_id}` | POST | Start test automation job |
| `/api/job/{job_id}` | GET | Poll job status |
| `/api/download/excel/{sid}/{jid}` | GET | Download results Excel |
| `/api/download/coverage/{sid}/{jid}` | GET | Download coverage report |
| `/api/download/test-file/{sid}/{jid}` | GET | Download .mldatx file |
| `/api/session/{session_id}` | DELETE | Clean up session files |

## Project Structure

```
SimulinkSample.slx              # Sample model (2 inputs: Throttle, Pedal → 2 outputs: Speed, Status)
sample_test_data.xlsx           # Sample Excel test data template
backend/
├── main.py                     # FastAPI backend with MATLAB Engine integration
├── requirements.txt            # Python dependencies
└── matlab_scripts/
    └── test_automation.m       # MATLAB helper for heavy Simulink Test API work
frontend/
├── package.json
├── public/index.html
└── src/
    ├── index.js
    ├── App.js                  # Main React component with stepper UI
    └── App.css                 # Professional dark theme styles
```

## Troubleshooting

### "No shared MATLAB session found"
Run `matlab.engine.shareEngine` in your MATLAB Command Window before starting the backend.

### "Simulink_Test license not available"
Ensure your MATLAB installation includes Simulink Test. Check with:
```matlab
license('test', 'Simulink_Test')
```

### Model has library dependencies
Ensure all required libraries are on the MATLAB path before running. The backend adds the upload directory to the MATLAB path automatically.

### Long execution times
Simulink simulations can take time. The backend runs them asynchronously — the UI polls for progress without freezing.
