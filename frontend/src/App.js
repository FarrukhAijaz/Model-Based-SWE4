import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const POLL_INTERVAL = 1500; // ms

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const api = axios.create({ baseURL: API_BASE });

function timeNow() {
  return new Date().toLocaleTimeString('en-US', { hour12: false });
}

// ── Stepper steps ──
const STEPS = [
  { id: 'upload',  label: 'Upload',     icon: '📁' },
  { id: 'analyze', label: 'Analyze',    icon: '🔍' },
  { id: 'testdata', label: 'Test Data', icon: '📊' },
  { id: 'execute', label: 'Execute',    icon: '▶️' },
  { id: 'report',  label: 'Report',     icon: '📋' },
];

// ===========================================================================
// Main App Component
// ===========================================================================
export default function App() {
  // Navigation state
  const [page, setPage] = useState('home'); // 'home', 'model-based', 'code-based'

  if (page === 'home') {
    return <HomePage onNavigate={setPage} />;
  }

  if (page === 'model-based') {
    return <ModelBasedPage onBackToHome={() => setPage('home')} />;
  }

  if (page === 'code-based') {
    return <CodeBasedPage onBackToHome={() => setPage('home')} />;
  }
}

// ===========================================================================
// Home Page Component
// ===========================================================================
function HomePage({ onNavigate }) {
  return (
    <div className="home-page">
      <div className="home-container">
        <img src={process.env.PUBLIC_URL + '/FO.png'} alt="Ford Otosan Logo" className="ford-logo-home" />
        <h1 className="app-title-home">Synapse Test Manager</h1>
        <p className="app-subtitle">
          <em>Automated Testing & Verification Platform</em>
        </p>
        <div className="version-home">v1.0.0</div>

        <div className="tiles-container">
          <div className="tile-card" onClick={() => onNavigate('model-based')}>
            <img src={process.env.PUBLIC_URL + '/matlab.svg'} alt="Model Based SWE4" className="tile-image" />
            <h2>Model Based SWE4</h2>
            <p>Simulink model testing & verification</p>
            <button className="tile-button">Start →</button>
          </div>

          <div className="tile-card" onClick={() => onNavigate('code-based')}>
            <img src={process.env.PUBLIC_URL + '/Cpp.png'} alt="Code Based SWE4" className="tile-image" />
            <h2>Code Based SWE4</h2>
            <p>C/C++ code testing & analysis</p>
            <button className="tile-button">Start →</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ===========================================================================
// Code Based Page Component
// ===========================================================================
function CodeBasedPage({ onBackToHome }) {
  return (
    <div className="app-container">
      {/* Header with back button */}
      <header className="app-header">
        <button className="btn btn-outline back-button" onClick={onBackToHome} style={{ marginRight: 'auto', marginBottom: 0 }}>
          ← Back to Home
        </button>
        <div style={{ textAlign: 'center', flex: 1 }}>
          <h1>Code Based SWE4</h1>
          <p>C/C++ Testing & Analysis</p>
        </div>
        <div style={{ width: 50 }}></div>
      </header>

      {/* Coming Soon content */}
      <div className="card" style={{ textAlign: 'center', maxWidth: 600, margin: '60px auto' }}>
        <div style={{ fontSize: 80, marginBottom: 20 }}>🚀</div>
        <h2 style={{ fontSize: 28, marginBottom: 10 }}>Coming Soon</h2>
        <p style={{ fontSize: 16, color: 'var(--text-secondary)', marginBottom: 20 }}>
          Code-based testing and C/C++ analysis features are under development.
        </p>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
          Check back soon for updates and features!
        </p>
      </div>
    </div>
  );
}

// ===========================================================================
// Model Based SWE4 Component
// ===========================================================================
function ModelBasedPage({ onBackToHome }) {
  // State
  const [health, setHealth] = useState(null);
  const [checkingHealth, setCheckingHealth] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [modelFile, setModelFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [templateConfig, setTemplateConfig] = useState({ num_scenarios: 5, start_time: '0', stop_time: '', time_step: '' });
  const [generatingTemplate, setGeneratingTemplate] = useState(false);
  const [templateInfo, setTemplateInfo] = useState(null);
  const [testDataFile, setTestDataFile] = useState(null);
  const [uploadingTestData, setUploadingTestData] = useState(false);
  const [testDataValidation, setTestDataValidation] = useState(null);
  const [options, setOptions] = useState({ coverage: true, output_report: true });
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);
  const [sampleAvailable, setSampleAvailable] = useState(false);
  const [sampleInfo, setSampleInfo] = useState(null);

  // Refs
  const logContainerRef = useRef(null);
  const pollRef = useRef(null);

  // Helper function to add logs
  const addLog = useCallback((type, message) => {
    setLogs(prev => [...prev, { type, message, time: timeNow() }]);
  }, []);

  // ── Health check & sample model info on mount ──
  useEffect(() => {
    const init = async () => {
      await checkHealth();
      
      try {
        const { data } = await api.get('/api/sample-files');
        setSampleAvailable(data.model_available);
        setSampleInfo(data);
      } catch {
        setSampleAvailable(false);
      }
    };
    
    init();
    
    // Poll health every 5 seconds
    const healthPoll = setInterval(checkHealth, 5000);
    return () => clearInterval(healthPoll);
  }, []);

  // ── Health check ──
  const checkHealth = useCallback(async () => {
    setCheckingHealth(true);
    try {
      const { data } = await api.get('/api/health');
      setHealth(data);
    } catch (err) {
      setHealth({ status: 'error', matlab_connected: false, message: err.message });
    } finally {
      setCheckingHealth(false);
    }
  }, []);

  // ── Upload handler ──
  const handleUpload = async () => {
    setUploading(true);
    setError(null);
    addLog('phase', 'Uploading model...');

    try {
      const formData = new FormData();
      formData.append('model_file', modelFile);
      const { data } = await api.post('/api/upload', formData);
      setSessionId(data.session_id);
      addLog('success', `Model uploaded (session: ${data.session_id})`);
      setCurrentStep(1);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      setError(`Upload failed: ${msg}`);
      addLog('error', `Upload failed: ${msg}`);
    } finally {
      setUploading(false);
    }
  };

  // ── Use Sample Model handler ──
  const handleUseSample = async () => {
    setUploading(true);
    setError(null);
    addLog('phase', 'Loading sample model (SimulinkSample.slx)...');

    try {
      const { data } = await api.post('/api/use-sample');
      setSessionId(data.session_id);
      setModelFile({ name: data.model_file });
      addLog('success', `Sample model loaded (session: ${data.session_id}) — ${data.model_file}`);
      setCurrentStep(1);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      setError(`Failed to load sample: ${msg}`);
      addLog('error', `Failed to load sample: ${msg}`);
    } finally {
      setUploading(false);
    }
  };

  // ── Analyze handler ──
  const handleAnalyze = async () => {
    if (!sessionId) return;
    setAnalyzing(true);
    setError(null);
    addLog('phase', 'Analyzing model...');

    try {
      const { data } = await api.post(`/api/analyze/${sessionId}`);
      setAnalysis(data);
      addLog('success', `Model "${data.model_name}" analyzed: ${data.inputs.length} inputs, ${data.outputs.length} outputs`);
      setCurrentStep(2); // Go to Test Data step
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      setError(`Analysis failed: ${msg}`);
      addLog('error', `Analysis failed: ${msg}`);
    } finally {
      setAnalyzing(false);
    }
  };

  // ── Generate Test Data Template handler ──
  const handleGenerateTemplate = async () => {
    if (!sessionId) return;
    setGeneratingTemplate(true);
    setError(null);
    addLog('phase', 'Generating Simulink Test-compliant Excel template...');

    try {
      const payload = {
        num_scenarios: parseInt(templateConfig.num_scenarios) || 5,
      };
      if (templateConfig.start_time !== '') {
        payload.start_time = parseFloat(templateConfig.start_time);
      }
      if (templateConfig.stop_time !== '') {
        payload.stop_time = parseFloat(templateConfig.stop_time);
      }
      if (templateConfig.time_step !== '') {
        payload.time_step = parseFloat(templateConfig.time_step);
      }
      const { data } = await api.post(`/api/generate-template/${sessionId}`, payload);
      setTemplateInfo(data);
      addLog('success', `Template generated: ${data.num_scenarios} scenarios with dummy data (${data.template_file})`);
      addLog('phase', 'Download the template, fill in your test data, then upload it back.');
      // Stay on Test Data step — do NOT advance until user uploads and validates
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      setError(`Template generation failed: ${msg}`);
      addLog('error', `Template generation failed: ${msg}`);
    } finally {
      setGeneratingTemplate(false);
    }
  };

  // ── Upload Test Data handler ──
  const handleUploadTestData = async () => {
    if (!sessionId || !testDataFile) return;
    setUploadingTestData(true);
    setError(null);
    setTestDataValidation(null);
    addLog('phase', `Uploading test data: ${testDataFile.name}...`);

    try {
      const formData = new FormData();
      formData.append('test_data_file', testDataFile);

      const { data } = await api.post(`/api/upload-test-data/${sessionId}`, formData);
      const validation = data.validation;
      setTestDataValidation(validation);

      if (validation.valid) {
        addLog('success', `Test data validated: ${validation.num_scenarios} scenario(s), all entries have data.`);
        addLog('phase', 'Test data is ready. Proceed to Execute.');
        setCurrentStep(3); // Advance to Execute
      } else {
        const errCount = validation.errors?.length || 0;
        addLog('error', `Validation failed: ${errCount} error(s) found. Fix the Excel and re-upload.`);
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      setError(`Upload failed: ${msg}`);
      addLog('error', `Upload failed: ${msg}`);
    } finally {
      setUploadingTestData(false);
    }
  };

  // ── Execute handler ──
  const handleExecute = async () => {
    if (!sessionId) return;
    setError(null);
    addLog('phase', 'Starting test execution...');

    try {
      const { data } = await api.post(`/api/run/${sessionId}`, options);
      setJobId(data.job_id);
      addLog('success', `Job queued: ${data.job_id}`);
      startPolling(data.job_id);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      setError(`Execution failed: ${msg}`);
      addLog('error', `Execution failed: ${msg}`);
    }
  };

  // ── Re-run (same data, re-execute) ──
  const handleRerun = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setJobId(null);
    setJobStatus(null);
    setError(null);
    setCurrentStep(3); // Go to Execute step
    addLog('phase', 'Ready to re-run tests with the same data.');
  };

  // ── Polling ──
  const startPolling = useCallback((jid) => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.get(`/api/job/${jid}`);
        setJobStatus(data);

        // Add log if phase changed
        if (data.message) {
          addLog('phase', data.message);
        }

        if (data.status === 'completed' || data.status === 'error') {
          clearInterval(pollRef.current);
          pollRef.current = null;

          if (data.status === 'completed') {
            addLog('success', 'Test automation completed!');
              setCurrentStep(4); // Report step
          } else {
            setError(data.error || 'Unknown error');
            addLog('error', data.error || 'Unknown error');
          }
        }
      } catch (err) {
        // Ignore polling errors
      }
    }, POLL_INTERVAL);
  }, [addLog]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // ── Reset ──
  const handleReset = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setCurrentStep(0);
    setModelFile(null);
    setSessionId(null);
    setAnalysis(null);
    setTemplateInfo(null);
    setTestDataFile(null);
    setUploadingTestData(false);
    setTestDataValidation(null);
    setTemplateConfig({ num_scenarios: 5, start_time: '0', stop_time: '', time_step: '' });
    setJobId(null);
    setJobStatus(null);
    setLogs([]);
    setError(null);
  };

  // ── Restart Session (back to Test Data step) ──
  const handleRestartSession = async () => {
    if (!sessionId) return;
    setError(null);
    addLog('phase', 'Restarting session — clearing test data and results...');

    try {
      await api.post(`/api/restart-session/${sessionId}`);
      if (pollRef.current) clearInterval(pollRef.current);
      setTemplateInfo(null);
      setTestDataFile(null);
      setUploadingTestData(false);
      setTestDataValidation(null);
      setTemplateConfig({ num_scenarios: 5, start_time: '0', stop_time: '', time_step: '' });
      setJobId(null);
      setJobStatus(null);
      setCurrentStep(2); // Go to Test Data step
      addLog('success', 'Session restarted. Configure and generate a new test data template.');
    } catch (err) {
      const msg = err.response?.data?.detail || err.message;
      setError(`Restart failed: ${msg}`);
      addLog('error', `Restart failed: ${msg}`);
    }
  };

  // ── Upload Modified Excel (skip template gen, go straight to upload) ──
  const handleUploadModifiedExcel = async () => {
    if (!sessionId) return;
    setError(null);

    // Clear previous results but keep template info for upload zone
    if (pollRef.current) clearInterval(pollRef.current);
    setTestDataFile(null);
    setUploadingTestData(false);
    setTestDataValidation(null);
    setJobId(null);
    setJobStatus(null);

    // If no template info, create a minimal one so the upload zone shows
    if (!templateInfo) {
      setTemplateInfo({
        template_file: 'Modified Excel Upload',
        num_scenarios: '?',
        inputs: analysis?.inputs?.map(i => i.name) || [],
        outputs: analysis?.outputs?.map(o => o.name) || [],
      });
    }

    setCurrentStep(2); // Go to Test Data step (upload zone will be visible)
    addLog('phase', 'Ready to upload modified Excel with updated test values.');
  };

  // ========================= RENDER =========================
  return (
    <div className="app-container">
      {/* Header with back button */}
      <header className="app-header">
        <button className="btn btn-outline back-button" onClick={onBackToHome} style={{ marginRight: 'auto', marginBottom: 0 }}>
          ← Back to Home
        </button>
        <div style={{ textAlign: 'center', flex: 1 }}>
          <h1>⚙ Simulink Test Automation</h1>
          <p>Automated unit testing via MATLAB Engine API</p>
        </div>
      </header>

      {/* Connection Banner */}
      <ConnectionBanner health={health} checking={checkingHealth} onRetry={checkHealth} />

      {/* Stepper */}
      <Stepper steps={STEPS} currentStep={currentStep} />

      {/* Step Content */}
      {currentStep === 0 && (
        <UploadCard
          modelFile={modelFile}
          onModelFile={setModelFile}
          onUpload={handleUpload}
          onUseSample={handleUseSample}
          sampleAvailable={sampleAvailable}
          sampleInfo={sampleInfo}
          uploading={uploading}
          disabled={!health?.matlab_connected}
        />
      )}

      {currentStep === 1 && (
        <AnalyzeCard
          analysis={analysis}
          analyzing={analyzing}
          onAnalyze={handleAnalyze}
        />
      )}

      {currentStep === 2 && (
        <TestDataCard
          analysis={analysis}
          sessionId={sessionId}
          templateInfo={templateInfo}
          generatingTemplate={generatingTemplate}
          onGenerateTemplate={handleGenerateTemplate}
          testDataFile={testDataFile}
          onTestDataFile={setTestDataFile}
          onUploadTestData={handleUploadTestData}
          uploadingTestData={uploadingTestData}
          testDataValidation={testDataValidation}
          templateConfig={templateConfig}
          onTemplateConfigChange={setTemplateConfig}
        />
      )}

      {currentStep === 3 && (
        <ExecuteCard
          analysis={analysis}
          options={options}
          onOptionsChange={setOptions}
          onExecute={handleExecute}
          jobStatus={jobStatus}
          sessionId={sessionId}
          jobId={jobId}
          templateInfo={templateInfo}
        />
      )}

      {currentStep === 4 && (
        <ReportCard
          jobStatus={jobStatus}
          sessionId={sessionId}
          jobId={jobId}
          onReset={handleReset}
          onRestartSession={handleRestartSession}
          onUploadModifiedExcel={handleUploadModifiedExcel}
          onRerun={handleRerun}
        />
      )}

      {/* Execution Log */}
      {logs.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-header">
            <div className="icon blue">📋</div>
            <h2>Activity Log</h2>
          </div>
          <div className="exec-log" ref={logContainerRef}>
            {logs.map((log, i) => (
              <div key={i} className="log-entry">
                <span className="log-time">{log.time}</span>
                <span className={`log-${log.type}`}>{log.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="error-box">
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  );
}

// ===========================================================================
// Sub-Components
// ===========================================================================

function ConnectionBanner({ health, checking, onRetry }) {
  if (checking) {
    return (
      <div className="connection-banner checking">
        <span className="status-dot blue" />
        Checking MATLAB connection...
      </div>
    );
  }

  if (!health || !health.matlab_connected) {
    return (
      <div className="connection-banner disconnected">
        <span className="status-dot red" />
        <span style={{ flex: 1 }}>
          MATLAB not connected. {health?.message || 'Run matlab.engine.shareEngine in MATLAB.'}
        </span>
        <button className="btn btn-outline" onClick={onRetry} style={{ padding: '4px 12px', fontSize: 12 }}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="connection-banner connected">
      <span className="status-dot green" />
      <span style={{ flex: 1 }}>
        MATLAB connected
        {health.available_sessions?.length > 0 && ` (${health.available_sessions[0]})`}
      </span>
      {health.licenses && (
        <div className="license-tags">
          {Object.entries(health.licenses).map(([name, ok]) => (
            <span key={name} className={`license-tag ${ok ? 'available' : 'unavailable'}`}>
              {name.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Stepper({ steps, currentStep }) {
  return (
    <div className="stepper">
      {steps.map((step, i) => (
        <div
          key={step.id}
          className={`step ${i === currentStep ? 'active' : ''} ${i < currentStep ? 'completed' : ''}`}
        >
          <div className="step-circle">
            {i < currentStep ? '✓' : step.icon}
          </div>
          <span className="step-label">{step.label}</span>
        </div>
      ))}
    </div>
  );
}

function UploadCard({ modelFile, onModelFile, onUpload, onUseSample, sampleAvailable, sampleInfo, uploading, disabled }) {
  const modelInputRef = useRef(null);

  return (
    <div className="card">
      <div className="card-header">
        <div className="icon blue">📁</div>
        <h2>Upload Model</h2>
      </div>

      {/* Quick-start: Use Sample Model */}
      {sampleAvailable && (
        <div className="sample-banner">
          <div className="sample-banner-content">
            <div className="sample-banner-icon">🚀</div>
            <div>
              <div className="sample-banner-title">Quick Start with Sample Model</div>
              <div className="sample-banner-desc">
                Use the pre-loaded <strong>SimulinkSample.slx</strong> (Throttle, Pedal → Speed, Status).
                Test data will be auto-generated in the next step.
              </div>
            </div>
          </div>
          <button
            className="btn btn-success"
            onClick={onUseSample}
            disabled={uploading || disabled}
            style={{ flexShrink: 0 }}
          >
            {uploading ? <><span className="spinner" /> Loading...</> : 'Use Sample Model'}
          </button>
        </div>
      )}

      {sampleAvailable && (
        <div className="divider-or"><span>OR upload your own model</span></div>
      )}

      {/* Model file */}
      <div
        className="upload-zone"
        onClick={() => modelInputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('drag-over'); }}
        onDragLeave={e => e.currentTarget.classList.remove('drag-over')}
        onDrop={e => {
          e.preventDefault();
          e.currentTarget.classList.remove('drag-over');
          const file = e.dataTransfer.files[0];
          if (file?.name.endsWith('.slx')) onModelFile(file);
        }}
      >
        <div className="upload-icon">📦</div>
        <div className="upload-text">
          {modelFile ? modelFile.name : 'Drop Simulink Model (.slx) here or click to browse'}
        </div>
        <div className="upload-hint">Accepts .slx files — test data will be auto-generated from the model</div>
        <input
          ref={modelInputRef}
          type="file"
          accept=".slx"
          style={{ display: 'none' }}
          onChange={e => e.target.files[0] && onModelFile(e.target.files[0])}
        />
      </div>

      {/* File tags */}
      <div>
        {modelFile && (
          <span className="file-tag">
            📦 {modelFile.name}
            <span className="remove" onClick={() => onModelFile(null)}>✕</span>
          </span>
        )}
      </div>

      <div className="btn-group">
        <button
          className="btn btn-primary"
          onClick={onUpload}
          disabled={!modelFile || uploading || disabled}
        >
          {uploading ? <><span className="spinner" /> Uploading...</> : 'Upload & Continue'}
        </button>
      </div>
    </div>
  );
}

function AnalyzeCard({ analysis, analyzing, onAnalyze }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="icon green">🔍</div>
        <h2>Model Analysis</h2>
      </div>

      {!analysis && (
        <>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 16 }}>
            Open the uploaded model and identify its inputs, outputs, and configuration.
          </p>
          <button className="btn btn-primary" onClick={onAnalyze} disabled={analyzing}>
            {analyzing ? <><span className="spinner" /> Analyzing...</> : 'Analyze Model'}
          </button>
        </>
      )}

      {analysis && (
        <>
          <div className="model-info-row">
            <div className="model-info-item">
              <span className="label">Model:</span>
              <span className="value">{analysis.model_name}</span>
            </div>
            <div className="model-info-item">
              <span className="label">Solver:</span>
              <span className="value">{analysis.solver}</span>
            </div>
            <div className="model-info-item">
              <span className="label">Stop Time:</span>
              <span className="value">{analysis.stop_time}s</span>
            </div>
            <div className="model-info-item">
              <span className="label">Step:</span>
              <span className="value">{analysis.fixed_step}</span>
            </div>
          </div>

          <div className="io-grid">
            <div className="io-section">
              <h3>Inputs ({analysis.inputs.length})</h3>
              {analysis.inputs.map((inp, i) => (
                <div key={i} className="io-item">
                  <span className="io-arrow">→</span>
                  <span className="io-name">{inp.name}</span>
                  <span className="io-type">{inp.dataType}</span>
                </div>
              ))}
            </div>
            <div className="io-section">
              <h3>Outputs ({analysis.outputs.length})</h3>
              {analysis.outputs.map((out, i) => (
                <div key={i} className="io-item">
                  <span className="io-arrow">←</span>
                  <span className="io-name">{out.name}</span>
                  <span className="io-type">{out.dataType}</span>
                </div>
              ))}
            </div>
          </div>

          {analysis.licenses && (
            <div style={{ marginTop: 16 }}>
              <div className="license-tags">
                {Object.entries(analysis.licenses).map(([name, ok]) => (
                  <span key={name} className={`license-tag ${ok ? 'available' : 'unavailable'}`}>
                    {name.replace(/_/g, ' ')}: {ok ? '✓' : '✕'}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function TestDataCard({
  analysis, sessionId, templateInfo, generatingTemplate, onGenerateTemplate,
  testDataFile, onTestDataFile, onUploadTestData, uploadingTestData, testDataValidation,
  templateConfig, onTemplateConfigChange,
}) {
  const fileInputRef = useRef(null);

  const handleConfigChange = (key, value) => {
    onTemplateConfigChange(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="icon orange">📊</div>
        <h2>Test Data</h2>
      </div>

      {/* Step 1: Generate template */}
      {!templateInfo && (
        <>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 12 }}>
            Configure test parameters and generate a <strong>Simulink Test-compliant Excel template</strong>.
            Each sheet represents a test scenario with time-series input data.
          </p>

          {analysis && (
            <div className="io-grid" style={{ marginBottom: 16 }}>
              <div className="io-section">
                <h3>Input Signals (columns in the template)</h3>
                {analysis.inputs.map((inp, i) => (
                  <div key={i} className="io-item">
                    <span className="io-arrow">→</span>
                    <span className="io-name">{inp.name}</span>
                    <span className="io-type">{inp.dataType}</span>
                  </div>
                ))}
              </div>
              <div className="io-section">
                <h3>Model Defaults</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Stop Time: {analysis.stop_time}s | Step: {analysis.fixed_step}</p>
              </div>
            </div>
          )}

          {/* Template Configuration */}
          <div className="template-config">
            <h3 style={{ fontSize: 15, marginBottom: 12, color: 'var(--text-primary)' }}>⚙ Template Configuration</h3>
            <div className="config-grid">
              <div className="config-field">
                <label>Number of Test Cases</label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={templateConfig.num_scenarios}
                  onChange={e => handleConfigChange('num_scenarios', e.target.value)}
                  placeholder="5"
                />
                <span className="config-hint">Sheets in Excel (1–100)</span>
              </div>
              <div className="config-field">
                <label>Start Time (s)</label>
                <input
                  type="number"
                  step="any"
                  min="0"
                  value={templateConfig.start_time}
                  onChange={e => handleConfigChange('start_time', e.target.value)}
                  placeholder="0"
                />
                <span className="config-hint">Simulation start</span>
              </div>
              <div className="config-field">
                <label>Stop Time (s)</label>
                <input
                  type="number"
                  step="any"
                  min="0"
                  value={templateConfig.stop_time}
                  onChange={e => handleConfigChange('stop_time', e.target.value)}
                  placeholder={analysis?.stop_time || '10'}
                />
                <span className="config-hint">Leave blank for model default ({analysis?.stop_time || '10'}s)</span>
              </div>
              <div className="config-field">
                <label>Time Step (s)</label>
                <input
                  type="number"
                  step="any"
                  min="0.001"
                  value={templateConfig.time_step}
                  onChange={e => handleConfigChange('time_step', e.target.value)}
                  placeholder="e.g. 0.1"
                />
                <span className="config-hint">Leave blank for 5 default points</span>
              </div>
            </div>
          </div>

          <div className="btn-group">
            <button
              className="btn btn-primary"
              onClick={onGenerateTemplate}
              disabled={generatingTemplate}
            >
              {generatingTemplate ? <><span className="spinner" /> Generating...</> : 'Generate Test Data Template'}
            </button>
          </div>
        </>
      )}

      {/* Step 2: Download template + Upload filled data */}
      {templateInfo && (
        <>
          <div className="sample-banner" style={{ background: 'var(--success-bg, #e8f5e9)', borderColor: 'var(--success-border, #4caf50)' }}>
            <div className="sample-banner-content">
              <div className="sample-banner-icon">✅</div>
              <div>
                <div className="sample-banner-title">Template Generated</div>
                <div className="sample-banner-desc">
                  <strong>{templateInfo.template_file}</strong> — {templateInfo.num_scenarios} test scenarios.
                  <br />
                  Inputs: {templateInfo.inputs?.join(', ')}
                  {templateInfo.outputs?.length > 0 && (<><br />Outputs: {templateInfo.outputs.join(', ')}</>)}
                </div>
              </div>
            </div>
          </div>

          {/* Instructions */}
          <div style={{
            background: 'var(--surface-bg, #f8f9fa)',
            border: '1px solid var(--border, #dee2e6)',
            borderRadius: 8,
            padding: '16px 20px',
            margin: '16px 0',
          }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 15 }}>📋 Steps to complete:</h3>
            <ol style={{ margin: 0, paddingLeft: 20, color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.8 }}>
              <li><strong>Download</strong> the template Excel below</li>
              <li><strong>Fill in</strong> your test data (Time + Input values for each scenario sheet)</li>
              <li><strong>Upload</strong> the filled file back — it will be validated automatically</li>
            </ol>
          </div>

          {/* Download button */}
          <div className="btn-group" style={{ marginBottom: 20 }}>
            <a
              href={`${API_BASE}/api/download/template/${sessionId}`}
              className="btn btn-success"
              download
            >
              📥 Download Template Excel
            </a>
          </div>

          {/* Upload zone */}
          <div
            className="upload-zone"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('drag-over'); }}
            onDragLeave={e => e.currentTarget.classList.remove('drag-over')}
            onDrop={e => {
              e.preventDefault();
              e.currentTarget.classList.remove('drag-over');
              const file = e.dataTransfer.files[0];
              if (file?.name.endsWith('.xlsx') || file?.name.endsWith('.xls')) onTestDataFile(file);
            }}
          >
            <div className="upload-icon">📄</div>
            <div className="upload-text">
              {testDataFile ? testDataFile.name : 'Drop your filled Excel file here, or click to browse'}
            </div>
            <div className="upload-hint">Upload the filled .xlsx with your test data for all scenarios</div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls"
              style={{ display: 'none' }}
              onChange={e => {
                if (e.target.files[0]) {
                  onTestDataFile(e.target.files[0]);
                  // Reset validation when new file selected
                }
              }}
            />
          </div>

          {testDataFile && (
            <div style={{ marginTop: 8 }}>
              <span className="file-tag">
                📄 {testDataFile.name}
                <span className="remove" onClick={() => { onTestDataFile(null); }}>✕</span>
              </span>
            </div>
          )}

          {/* Upload & Validate button */}
          <div className="btn-group" style={{ marginTop: 16 }}>
            <button
              className="btn btn-primary"
              onClick={onUploadTestData}
              disabled={!testDataFile || uploadingTestData}
            >
              {uploadingTestData ? <><span className="spinner" /> Uploading & Validating...</> : 'Upload & Validate Test Data'}
            </button>
          </div>

          {/* Validation results */}
          {testDataValidation && (
            <div style={{
              marginTop: 16,
              padding: '12px 16px',
              borderRadius: 8,
              border: `1px solid ${testDataValidation.valid ? '#4caf50' : '#f44336'}`,
              background: testDataValidation.valid ? '#e8f5e9' : '#ffebee',
            }}>
              {testDataValidation.valid ? (
                <>
                  <div style={{ fontWeight: 600, color: '#2e7d32', marginBottom: 4 }}>
                    ✅ Validation Passed
                  </div>
                  <div style={{ fontSize: 13, color: '#555' }}>
                    {testDataValidation.num_scenarios} scenario(s) with all entries filled.
                    Proceeding to Execute step...
                  </div>
                </>
              ) : (
                <>
                  <div style={{ fontWeight: 600, color: '#c62828', marginBottom: 8 }}>
                    ❌ Validation Failed
                  </div>
                  <div style={{ fontSize: 13, color: '#555', marginBottom: 8 }}>
                    Please fix the following issues and re-upload:
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: '#c62828' }}>
                    {testDataValidation.errors?.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                  {testDataValidation.warnings?.length > 0 && (
                    <>
                      <div style={{ fontSize: 13, color: '#ef6c00', marginTop: 8, fontWeight: 600 }}>
                        ⚠️ Warnings:
                      </div>
                      <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: '#ef6c00' }}>
                        {testDataValidation.warnings.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </>
                  )}

                  {/* Per-sheet details */}
                  {testDataValidation.sheets?.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#555', marginBottom: 4 }}>
                        Sheet details:
                      </div>
                      {testDataValidation.sheets.map((sheet, i) => (
                        <div key={i} style={{
                          fontSize: 12,
                          color: sheet.errors?.length > 0 ? '#c62828' : '#2e7d32',
                          padding: '2px 0',
                        }}>
                          {sheet.errors?.length > 0 ? '❌' : '✅'} <strong>{sheet.name}</strong>:&nbsp;
                          {sheet.rows} rows, columns: [{sheet.columns?.join(', ')}]
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ExecuteCard({ analysis, options, onOptionsChange, onExecute, jobStatus, sessionId, jobId, templateInfo }) {
  const isRunning = jobStatus && !['completed', 'error'].includes(jobStatus.status);

  const handleOption = (key, value) => {
    onOptionsChange(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="icon purple">▶️</div>
        <h2>Execute Tests</h2>
      </div>

      {/* Options */}
      {!isRunning && !jobStatus?.result && (
        <>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 12 }}>
            Configure and run the test automation pipeline (Harness → Test File → Run → Coverage).
            {templateInfo && (
              <span> Using <strong>{templateInfo.num_scenarios}</strong> test scenarios from <strong>{templateInfo.template_file}</strong>.</span>
            )}
          </p>

          <div className="options-grid">
            <label className="option-item">
              <input
                type="checkbox"
                checked={options.cleanup_harness}
                onChange={e => handleOption('cleanup_harness', e.target.checked)}
              />
              Clean up harness after run
            </label>
            <label className="option-item">
              <input
                type="checkbox"
                checked={options.cleanup_test_file}
                onChange={e => handleOption('cleanup_test_file', e.target.checked)}
              />
              Clean up .mldatx after run
            </label>
          </div>

          <div className="btn-group">
            <button className="btn btn-primary" onClick={onExecute}>
              Run Test Automation
            </button>
          </div>
        </>
      )}

      {/* Progress */}
      {jobStatus && (
        <div className="progress-container">
          <div className="progress-bar-bg">
            <div
              className="progress-bar-fill"
              style={{ width: `${jobStatus.progress || 0}%` }}
            />
          </div>
          <div className="progress-label">
            <span>{jobStatus.current_phase}</span>
            <span>{jobStatus.progress}%</span>
          </div>
        </div>
      )}
    </div>
  );
}

function ReportCard({ jobStatus, sessionId, jobId, onReset, onRestartSession, onUploadModifiedExcel, onRerun }) {
  const [expandedRows, setExpandedRows] = React.useState({});

  const toggleRow = (idx) => {
    setExpandedRows(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  if (!jobStatus?.result) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="icon orange">📊</div>
          <h2>Results</h2>
        </div>
        <p style={{ color: 'var(--text-secondary)' }}>No results available yet.</p>
      </div>
    );
  }

  const result = jobStatus.result;
  const execPhase = result.phases?.execution || {};
  const testCases = execPhase.testCases || [];
  const passed = testCases.filter(tc => tc.outcome === 'Passed').length;
  const failed = testCases.filter(tc => tc.outcome !== 'Passed').length;

  // Collect input/output column names from first test case
  const firstTC = testCases[0] || {};
  const inputNames = firstTC.inputValues ? Object.keys(firstTC.inputValues) : [];
  const outputNames = firstTC.expectedOutputs ? Object.keys(firstTC.expectedOutputs) : [];

  // Total columns for colspan
  const totalCols = 3 + inputNames.length + outputNames.length * 2 + 1; // #, name, expand, inputs, exp, act, outcome

  return (
    <div className="card">
      <div className="card-header">
        <div className="icon orange">📊</div>
        <h2>Test Results</h2>
      </div>

      {/* Summary stats */}
      <div className="results-summary">
        <div className="result-stat total">
          <div className="stat-value">{testCases.length}</div>
          <div className="stat-label">Total Tests</div>
        </div>
        <div className="result-stat passed">
          <div className="stat-value">{passed}</div>
          <div className="stat-label">Passed</div>
        </div>
        <div className="result-stat failed">
          <div className="stat-value">{failed}</div>
          <div className="stat-label">Failed</div>
        </div>
        <div className={`result-stat ${execPhase.overallOutcome === 'Passed' ? 'passed' : 'failed'}`}>
          <div className="stat-value" style={{ fontSize: 18 }}>
            {execPhase.overallOutcome || 'N/A'}
          </div>
          <div className="stat-label">Overall</div>
        </div>
      </div>

      {/* Test case table with expandable per-time-step details */}
      {testCases.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
        <table className="test-table">
          <thead>
            <tr>
              <th style={{ width: 30 }}></th>
              <th>#</th>
              <th>Test Case</th>
              {inputNames.map(n => <th key={`in-${n}`}>{n}</th>)}
              {outputNames.map(n => <th key={`exp-${n}`}>Expected {n}</th>)}
              {outputNames.map(n => <th key={`act-${n}`}>Actual {n}</th>)}
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {testCases.map((tc, i) => {
              const hasTimeSteps = tc.timeSteps && tc.timeSteps.length > 0;
              const isExpanded = expandedRows[i];
              const failedStepCount = tc.failedSteps || 0;
              const totalStepCount = tc.totalSteps || (tc.timeSteps?.length || 0);

              return (
                <React.Fragment key={i}>
                  {/* Summary row */}
                  <tr
                    className={`tc-summary-row ${hasTimeSteps ? 'expandable' : ''}`}
                    onClick={() => hasTimeSteps && toggleRow(i)}
                    style={{ cursor: hasTimeSteps ? 'pointer' : 'default' }}
                  >
                    <td style={{ textAlign: 'center', fontSize: 16, width: 30 }}>
                      {hasTimeSteps ? (isExpanded ? '▼' : '▶') : ''}
                    </td>
                    <td>{i + 1}</td>
                    <td>
                      {tc.name}
                      {hasTimeSteps && (
                        <span style={{ fontSize: 11, color: '#888', marginLeft: 6 }}>
                          ({totalStepCount} steps{failedStepCount > 0 ? `, ${failedStepCount} failed` : ''})
                        </span>
                      )}
                    </td>
                    {inputNames.map(n => (
                      <td key={`in-${n}`}>
                        {tc.inputValues?.[n] != null ? Number(tc.inputValues[n]).toFixed(2) : 'N/A'}
                      </td>
                    ))}
                    {outputNames.map(n => (
                      <td key={`exp-${n}`}>
                        {tc.expectedOutputs?.[n] != null && !isNaN(tc.expectedOutputs[n])
                          ? Number(tc.expectedOutputs[n]).toFixed(4) : 'N/A'}
                      </td>
                    ))}
                    {outputNames.map(n => (
                      <td key={`act-${n}`}>
                        {tc.actualOutputs?.[n] != null && !isNaN(tc.actualOutputs[n])
                          ? Number(tc.actualOutputs[n]).toFixed(4) : 'N/A'}
                      </td>
                    ))}
                    <td>
                      <span className={`badge ${tc.outcome?.toLowerCase()}`}>
                        {tc.outcome}
                      </span>
                    </td>
                  </tr>

                  {/* Expanded per-time-step rows */}
                  {isExpanded && hasTimeSteps && (
                    <>
                      <tr className="timestep-header-row">
                        <td></td>
                        <td style={{ fontWeight: 600, fontSize: 11, color: '#666' }}>Time</td>
                        <td style={{ fontWeight: 600, fontSize: 11, color: '#666' }}>Step</td>
                        {inputNames.map(n => (
                          <td key={`th-in-${n}`} style={{ fontWeight: 600, fontSize: 11, color: '#666' }}>{n}</td>
                        ))}
                        {outputNames.map(n => (
                          <td key={`th-exp-${n}`} style={{ fontWeight: 600, fontSize: 11, color: '#666' }}>Exp {n}</td>
                        ))}
                        {outputNames.map(n => (
                          <td key={`th-act-${n}`} style={{ fontWeight: 600, fontSize: 11, color: '#666' }}>Act {n}</td>
                        ))}
                        <td style={{ fontWeight: 600, fontSize: 11, color: '#666' }}>Row</td>
                      </tr>
                      {tc.timeSteps.map((step, si) => {
                        const rowFailed = step.rowMatch === false;
                        return (
                          <tr
                            key={`step-${i}-${si}`}
                            className={`timestep-row ${rowFailed ? 'row-failed' : 'row-passed'}`}
                          >
                            <td></td>
                            <td style={{ fontSize: 12, color: '#555' }}>{Number(step.time).toFixed(2)}</td>
                            <td style={{ fontSize: 12, color: '#888' }}>#{si + 1}</td>
                            {inputNames.map(n => (
                              <td key={`s-in-${n}`} style={{ fontSize: 12 }}>
                                {step.inputs?.[n] != null && !isNaN(step.inputs[n])
                                  ? Number(step.inputs[n]).toFixed(2) : 'N/A'}
                              </td>
                            ))}
                            {outputNames.map(n => (
                              <td key={`s-exp-${n}`} style={{ fontSize: 12 }}>
                                {step.expected?.[n] != null && !isNaN(step.expected[n])
                                  ? Number(step.expected[n]).toFixed(4) : 'N/A'}
                              </td>
                            ))}
                            {outputNames.map(n => (
                              <td key={`s-act-${n}`} style={{ fontSize: 12 }}>
                                {step.actual?.[n] != null && !isNaN(step.actual[n])
                                  ? Number(step.actual[n]).toFixed(4) : 'N/A'}
                              </td>
                            ))}
                            <td>
                              <span className={`badge-sm ${rowFailed ? 'failed' : 'passed'}`}>
                                {rowFailed ? '✗' : '✓'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
        </div>
      )}

      {/* Downloads */}
      <div className="btn-group">
        <a
          href={`${API_BASE}/api/download/excel/${sessionId}/${jobId}`}
          className="btn btn-success"
          download
        >
          📥 Download Results Excel
        </a>
        {execPhase.coverageAvailable && (
          <a
            href={`${API_BASE}/api/download/coverage/${sessionId}/${jobId}`}
            className="btn btn-primary"
            download
          >
            📥 Download Coverage Report
          </a>
        )}
        <a
          href={`${API_BASE}/api/download/test-file/${sessionId}/${jobId}`}
          className="btn btn-outline"
          download
        >
          📥 Download .mldatx
        </a>
        <button className="btn btn-outline" onClick={onReset}>
          🔄 Start New Session
        </button>
        <button className="btn btn-primary" onClick={onRerun}>
          🔁 Re-run Tests
        </button>
        <button className="btn btn-primary" onClick={onRestartSession}>
          📝 Re-test with New Template
        </button>
        <button className="btn btn-warning" onClick={onUploadModifiedExcel}>
          📤 Upload Modified Excel
        </button>
      </div>
    </div>
  );
}
