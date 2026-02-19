% RUN_VALIDATION - Standalone script to validate test_automation pipeline
%
% Run this script from the MATLAB Command Window with your working
% directory set to the Simulink project folder.
%
%   >> cd('/home/saijaz/Desktop/Simulink')
%   >> run_validation
%
% It will invoke test_automation() against SimulinkSample.slx using
% sample_test_data.xlsx and produce results under ./test_output/

clc;
fprintf('============================================================\n');
fprintf('  Simulink Test Automation — Validation Runner\n');
fprintf('============================================================\n\n');

%% ── Paths ──────────────────────────────────────────────────────────────
rootDir   = fileparts(mfilename('fullpath'));
if isempty(rootDir), rootDir = pwd; end

modelPath = fullfile(rootDir, 'SimulinkSample.slx');
excelPath = fullfile(rootDir, 'sample_test_data.xlsx');
outputDir = fullfile(rootDir, 'test_output');
scriptsDir = fullfile(rootDir, 'backend', 'matlab_scripts');

% Add scripts directory to path so test_automation() is found
addpath(scriptsDir);

%% ── Validate prerequisites ────────────────────────────────────────────
assert(exist(modelPath, 'file') == 4, ...
    'Model not found: %s', modelPath);
assert(exist(excelPath, 'file') == 2, ...
    'Excel file not found: %s', excelPath);
assert(exist(fullfile(scriptsDir, 'test_automation.m'), 'file') == 2, ...
    'test_automation.m not found in %s', scriptsDir);

fprintf('  Model : %s\n', modelPath);
fprintf('  Excel : %s\n', excelPath);
fprintf('  Output: %s\n\n', outputDir);

%% ── Run the pipeline ──────────────────────────────────────────────────
opts = struct();
opts.cleanupHarness  = false;   % keep harness for inspection
opts.cleanupTestFile = false;   % keep .mldatx for inspection

tic;
results = test_automation(modelPath, excelPath, outputDir, opts);
elapsed = toc;

%% ── Display summary ───────────────────────────────────────────────────
fprintf('\n============================================================\n');
fprintf('  VALIDATION SUMMARY  (%.1fs)\n', elapsed);
fprintf('============================================================\n');

if results.success
    fprintf('  Status  : SUCCESS\n');
else
    fprintf('  Status  : FAILED\n');
    fprintf('  Error   : %s\n', results.error);
    if isfield(results, 'errorStack')
        for k = 1:length(results.errorStack)
            fprintf('    %s\n', results.errorStack{k});
        end
    end
end

% Licenses
if isfield(results, 'licenses')
    fprintf('\n  Licenses:\n');
    fprintf('    Simulink          : %d\n', results.licenses.Simulink);
    fprintf('    Simulink Test     : %d\n', results.licenses.Simulink_Test);
    fprintf('    Simulink Coverage : %d\n', results.licenses.Simulink_Coverage);
end

% Analysis
if isfield(results, 'phases') && isfield(results.phases, 'analysis')
    a = results.phases.analysis;
    fprintf('\n  Analysis:\n');
    fprintf('    Inputs  : %s\n', strjoin({a.inputs.name}, ', '));
    fprintf('    Outputs : %s\n', strjoin({a.outputs.name}, ', '));
    fprintf('    Solver  : %s | StopTime %s | FixedStep %s\n', ...
        a.solverName, a.stopTime, a.fixedStep);
end

% Execution
if isfield(results, 'phases') && isfield(results.phases, 'execution')
    ex = results.phases.execution;
    fprintf('\n  Execution:\n');
    fprintf('    Overall : %s\n', ex.overallOutcome);
    if ~isempty(ex.caseOutcomes)
        for c = 1:size(ex.caseOutcomes, 1)
            fprintf('    %s  →  %s\n', ex.caseOutcomes{c, 1}, ex.caseOutcomes{c, 2});
        end
    end
end

% Coverage
if isfield(results, 'phases') && isfield(results.phases, 'coverage')
    cov = results.phases.coverage;
    fprintf('\n  Coverage:\n');
    if cov.available
        fprintf('    Report : %s\n', cov.reportPath);
    else
        fprintf('    Not available');
        if isfield(cov, 'error')
            fprintf(' — %s', cov.error);
        end
        fprintf('\n');
    end
end

% Export
if isfield(results, 'phases') && isfield(results.phases, 'export')
    fprintf('\n  Exported Excel: %s\n', results.phases.export.excelPath);
end

fprintf('\n============================================================\n');
fprintf('  Artifacts in: %s\n', outputDir);
fprintf('============================================================\n');
