function results = test_automation(modelPath, excelPath, outputDir, options)
% TEST_AUTOMATION - Automates Simulink unit testing workflow
%
% Pipeline:
%   Phase 1: Model Analysis (identify inputs/outputs)
%   Phase 2: Harness Creation (sltest.harness.create)
%   Phase 3: Test Generation (create .mldatx from Simulink Test-compliant Excel)
%   Phase 4: Execution & Coverage (run tests with Decision/Condition/MCDC)
%   Phase 5: Results export to Excel & Coverage HTML
%
% INPUTS:
%   modelPath  - Full path to the .slx model file
%   excelPath  - Full path to the Simulink Test-compliant Excel file
%                (each sheet = one test scenario; columns: Time, Input1, Input2, ...)
%   outputDir  - Directory for output artifacts
%   options    - (optional) Struct with fields:
%                .cleanupHarness  (logical) - Remove harness after run
%                .cleanupTestFile (logical) - Remove .mldatx after run
%                .stopTime        (char)    - Override simulation stop time
%                .fixedStep       (char)    - Override fixed step size
%
% OUTPUT:
%   results    - Struct containing all test results and metadata

    %% ==================== INITIALIZATION ====================
    if nargin < 4, options = struct(); end
    if ~isfield(options, 'cleanupHarness'),  options.cleanupHarness  = false; end
    if ~isfield(options, 'cleanupTestFile'), options.cleanupTestFile = false; end
    if ~isfield(options, 'stopTime'),        options.stopTime        = '';    end
    if ~isfield(options, 'fixedStep'),       options.fixedStep       = '';    end

    results          = struct();
    results.success  = false;
    results.error    = '';
    results.phases   = struct();

    try
        %% ==================== LICENSE CHECK ====================
        fprintf('==========================================================\n');
        fprintf('[Phase 0] Checking required licenses...\n');
        fprintf('==========================================================\n');

        hasSimulink = license('test', 'Simulink');
        hasSlTest   = license('test', 'Simulink_Test');
        hasSlCov    = license('test', 'Simulink_Coverage');

        results.licenses.Simulink          = hasSimulink;
        results.licenses.Simulink_Test     = hasSlTest;
        results.licenses.Simulink_Coverage = hasSlCov;

        if ~hasSimulink
            error('TEST_AUTOMATION:NoLicense', 'Simulink license not available.');
        end
        if ~hasSlTest
            error('TEST_AUTOMATION:NoLicense', 'Simulink Test license not available.');
        end
        if ~hasSlCov
            warning('TEST_AUTOMATION:NoLicense', ...
                'Simulink Coverage license not available. Coverage will be skipped.');
        end

        fprintf('  Simulink: %d | Simulink Test: %d | Simulink Coverage: %d\n', ...
            hasSimulink, hasSlTest, hasSlCov);

        %% ==================== PHASE 1: MODEL ANALYSIS ====================
        fprintf('\n==========================================================\n');
        fprintf('[Phase 1] Analyzing model...\n');
        fprintf('==========================================================\n');

        [modelDir, modelName, ~] = fileparts(modelPath);

        % Remove any shadowing paths that contain the same model file
        try
            pathList = strsplit(path, pathsep);
            for pi = 1:length(pathList)
                p = pathList{pi};
                if exist(fullfile(p, [modelName '.slx']), 'file') && ~strcmp(p, modelDir)
                    rmpath(p);
                    fprintf('  Removed shadowing path: %s\n', p);
                end
            end
        catch
        end

        % Add model directory to MATLAB path so dependencies are found
        if ~isempty(modelDir)
            addpath(modelDir);
            fprintf('  Added to path: %s\n', modelDir);
        end

        % Create output directory
        if ~exist(outputDir, 'dir')
            mkdir(outputDir);
            fprintf('  Created output dir: %s\n', outputDir);
        end

        % Close model if already loaded (clean slate)
        if bdIsLoaded(modelName)
            close_system(modelName, 0);
        end

        % Load the model
        load_system(modelPath);
        fprintf('  Model "%s" loaded successfully.\n', modelName);

        % ── Identify root-level Inports ──
        inportBlocks = find_system(modelName, 'SearchDepth', 1, 'BlockType', 'Inport');
        inputInfo = struct('name', {}, 'port', {}, 'dataType', {});
        for i = 1:length(inportBlocks)
            inputInfo(i).name     = get_param(inportBlocks{i}, 'Name');
            inputInfo(i).port     = get_param(inportBlocks{i}, 'Port');
            inputInfo(i).dataType = get_param(inportBlocks{i}, 'OutDataTypeStr');
            fprintf('  Input  %d: "%s"  (Type: %s, Port: %s)\n', ...
                i, inputInfo(i).name, inputInfo(i).dataType, inputInfo(i).port);
        end

        % ── Identify root-level Outports ──
        outportBlocks = find_system(modelName, 'SearchDepth', 1, 'BlockType', 'Outport');
        outputInfo = struct('name', {}, 'port', {}, 'dataType', {});
        for i = 1:length(outportBlocks)
            outputInfo(i).name     = get_param(outportBlocks{i}, 'Name');
            outputInfo(i).port     = get_param(outportBlocks{i}, 'Port');
            outputInfo(i).dataType = get_param(outportBlocks{i}, 'OutDataTypeStr');
            fprintf('  Output %d: "%s"  (Type: %s, Port: %s)\n', ...
                i, outputInfo(i).name, outputInfo(i).dataType, outputInfo(i).port);
        end

        % Solver info
        mdlStopTime  = get_param(modelName, 'StopTime');
        mdlFixedStep = get_param(modelName, 'FixedStep');
        mdlSolver    = get_param(modelName, 'SolverName');

        results.phases.analysis.inputs     = inputInfo;
        results.phases.analysis.outputs    = outputInfo;
        results.phases.analysis.modelName  = modelName;
        results.phases.analysis.stopTime   = mdlStopTime;
        results.phases.analysis.fixedStep  = mdlFixedStep;
        results.phases.analysis.solverName = mdlSolver;

        fprintf('  Solver: %s | StopTime: %s | FixedStep: %s\n', ...
            mdlSolver, mdlStopTime, mdlFixedStep);

        inputNames  = {inputInfo.name};
        inputDTypes = {inputInfo.dataType};
        outputNames = {outputInfo.name};

        %% ==================== PHASE 2: HARNESS CREATION ====================
        fprintf('\n==========================================================\n');
        fprintf('[Phase 2] Creating test harness...\n');
        fprintf('==========================================================\n');

        harnessName = [modelName '_AutoHarness'];

        % Delete existing harness with same name
        try
            existingHarnesses = sltest.harness.find(modelName);
            for h = 1:length(existingHarnesses)
                if strcmp(existingHarnesses(h).name, harnessName)
                    fprintf('  Removing existing harness "%s"...\n', harnessName);
                    sltest.harness.delete(modelName, harnessName);
                    break;
                end
            end
        catch
            % No existing harnesses — continue
        end

        % Create harness with Inport source / Outport sink
        % First enable signal logging on output port lines
        outPorts = find_system(modelName, 'SearchDepth', 1, 'BlockType', 'Outport');
        for oIdx = 1:length(outPorts)
            blk = outPorts{oIdx};
            ph = get_param(blk, 'PortHandles');
            lineH = get_param(ph.Inport, 'Line');
            if lineH ~= -1
                srcPort = get_param(lineH, 'SrcPortHandle');
                if srcPort ~= -1
                    portName = get_param(blk, 'Name');
                    set_param(srcPort, 'DataLogging', 'on');
                    set_param(srcPort, 'DataLoggingNameMode', 'Custom');
                    set_param(srcPort, 'DataLoggingName', portName);
                    fprintf('  Signal logging enabled for: %s\n', portName);
                end
            end
        end

        % Force fixed-step solver so output time points match input data
        % Detect time step from Excel Time column
        timeStepVal = '';
        if isfield(opts, 'fixedStep') && ~isempty(opts.fixedStep)
            timeStepVal = opts.fixedStep;
        else
            try
                sheets = sheetnames(excelPath);
                T = readtable(excelPath, 'Sheet', sheets{1});
                if ismember('Time', T.Properties.VariableNames) && height(T) >= 2
                    timeStepVal = num2str(T.Time(2) - T.Time(1));
                end
            catch
            end
        end
        if isempty(timeStepVal)
            timeStepVal = '0.1';
        end
        set_param(modelName, 'SolverType', 'Fixed-step');
        set_param(modelName, 'Solver', 'FixedStepDiscrete');
        set_param(modelName, 'FixedStep', timeStepVal);
        fprintf('  Solver set to Fixed-step (FixedStepDiscrete) with step = %s\n', timeStepVal);

        save_system(modelName);

        sltest.harness.create(modelName, ...
            'Name',              harnessName, ...
            'Source',            'Inport', ...
            'Sink',             'Outport', ...
            'VerificationMode', 'Normal', ...
            'LogOutputs',       true, ...
            'RebuildOnOpen',    true);

        fprintf('  Harness "%s" created.\n', harnessName);
        results.phases.harness.name    = harnessName;
        results.phases.harness.created = true;

        % Verify harness exists
        hList = sltest.harness.find(modelName);
        found = false;
        for h = 1:length(hList)
            if strcmp(hList(h).name, harnessName)
                found = true;
                fprintf('  Harness verified in model.\n');
                break;
            end
        end
        if ~found
            error('TEST_AUTOMATION:HarnessNotFound', ...
                'Harness "%s" was not found after creation.', harnessName);
        end

        %% ==================== PHASE 3: TEST GENERATION ====================
        fprintf('\n==========================================================\n');
        fprintf('[Phase 3] Generating test file from Simulink Test-compliant Excel...\n');
        fprintf('==========================================================\n');

        % ── Read Excel sheet info ──
        sheetNames   = cellstr(sheetnames(excelPath));
        numScenarios = length(sheetNames);
        fprintf('  Excel file: %s\n', excelPath);
        fprintf('  Number of sheets (scenarios): %d\n', numScenarios);
        for si = 1:numScenarios
            fprintf('    Sheet %d: "%s"\n', si, sheetNames{si});
        end

        % ── Simulation parameters ──
        simStopTime = mdlStopTime;
        if ~isempty(options.stopTime), simStopTime = options.stopTime; end

        % ── Create .mldatx test file ──
        testFileName = [modelName '_AutoTest.mldatx'];
        testFilePath = fullfile(outputDir, testFileName);

        if exist(testFilePath, 'file')
            delete(testFilePath);
            fprintf('  Removed old test file.\n');
        end

        % Clear Test Manager state
        sltest.testmanager.clear();
        sltest.testmanager.clearResults();

        % Create test file → suite
        tf = sltest.testmanager.TestFile(testFilePath);
        ts = tf.getTestSuites();
        if isempty(ts)
            ts = tf.createTestSuite([modelName '_TestSuite']);
        else
            ts = ts(1);
            ts.Name = [modelName '_TestSuite'];
        end

        % Remove any default test cases that were auto-created
        defaultTCs = ts.getTestCases();
        for dci = 1:length(defaultTCs)
            defaultTCs(dci).remove();
        end

        % ── Create one test case per Excel sheet (scenario) ──
        for sc = 1:numScenarios
            sheetName = sheetNames{sc};
            tcName = sprintf('%s_TC_%d_%s', modelName, sc, sheetName);
            tc = ts.createTestCase('baseline', tcName);
            tc.setProperty('model', modelName);
            tc.setProperty('HarnessName', harnessName, 'HarnessOwner', modelName);
            tc.setProperty('StopTime', str2double(simStopTime));

            % Enable coverage
            if hasSlCov
                try
                    covSettings = tc.getCoverageSettings();
                    covSettings.RecordCoverage = true;
                    covSettings.MdlRefCoverage = true;
                    covSettings.MetricSettings = 'dcme';
                    fprintf('  TC %d: Coverage enabled (dcme)\n', sc);
                catch covEx
                    fprintf('  TC %d: Coverage config warning: %s\n', sc, covEx.message);
                end
            end

            % ── Read scenario data from this sheet ──
            scenarioData = readtable(excelPath, 'Sheet', sheetName, 'VariableNamingRule', 'preserve');
            scenarioCols = scenarioData.Properties.VariableNames;
            fprintf('  Sheet "%s": %d rows x %d columns\n', sheetName, height(scenarioData), width(scenarioData));

            % Get time vector
            if ismember('Time', scenarioCols)
                timeVec = scenarioData.Time;
            else
                % Default time vector if no Time column
                timeVec = linspace(0, str2double(simStopTime), height(scenarioData))';
            end

            % Build input Dataset from the time-series data
            inputDS = Simulink.SimulationData.Dataset;
            for inp = 1:length(inputNames)
                inpName = inputNames{inp};
                if ismember(inpName, scenarioCols)
                    vals = scenarioData.(inpName);
                    if iscell(vals)
                        vals = cellfun(@(x) str2double(string(x)), vals);
                    end
                    % Cast to the data type expected by the inport
                    inpDType = inputDTypes{inp};
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
                    fprintf('  TC %d, Input "%s": %d time-series points\n', sc, inpName, length(vals));
                else
                    fprintf('  TC %d, Input "%s" — MISSING in sheet "%s"\n', sc, inpName, sheetName);
                end
            end

            % Read expected output columns (Expected_<name>) for pass/fail comparison
            if ~exist('expectedOutputs', 'var')
                expectedOutputs = cell(numScenarios, length(outputNames));
            end
            for oi = 1:length(outputNames)
                expColName = ['Expected_' outputNames{oi}];
                if ismember(expColName, scenarioCols)
                    vals = scenarioData.(expColName);
                    if iscell(vals)
                        vals = cellfun(@(x) str2double(string(x)), vals);
                    end
                    expectedOutputs{sc, oi} = double(vals(end));
                    fprintf('  TC %d, Expected "%s": %.4f\n', sc, outputNames{oi}, double(vals(end)));
                else
                    expectedOutputs{sc, oi} = NaN;
                end
            end

            % Store input values summary for results reporting
            if ~exist('inputValuesSummary', 'var')
                inputValuesSummary = cell(numScenarios, length(inputNames));
            end
            for ini = 1:length(inputNames)
                inpName = inputNames{ini};
                if ismember(inpName, scenarioCols)
                    vals = scenarioData.(inpName);
                    if iscell(vals)
                        vals = cellfun(@(x) str2double(string(x)), vals);
                    end
                    inputValuesSummary{sc, ini} = double(vals(end));
                else
                    inputValuesSummary{sc, ini} = NaN;
                end
            end

            % Save input Dataset to MAT file and add as external input
            matFilePath = fullfile(outputDir, sprintf('input_scenario_%d.mat', sc));
            inputData = inputDS; %#ok<NASGU>
            save(matFilePath, 'inputData');
            testInput = tc.addInput(matFilePath);
            % Map the input signals to model inports by block name
            map(testInput, 'Mode', 0);
            fprintf('  Scenario %d: Input mapped (MappingStatus=%s)\n', sc, testInput.MappingStatus);

            % --- Add baseline criteria by creating a baseline MAT file directly ---
            try
                % Build a baseline Dataset from expected output values
                baselineDS = Simulink.SimulationData.Dataset;
                baselineDS.Name = 'baselineData';
                hasExpected = false;

                for oi = 1:length(outputNames)
                    expColName = ['Expected_' outputNames{oi}];
                    if ismember(expColName, scenarioCols)
                        expVals = scenarioData.(expColName);
                        if iscell(expVals)
                            expVals = cellfun(@(x) str2double(string(x)), expVals);
                        end
                        bSig = timeseries(double(expVals), double(timeVec));
                        bSig.Name = outputNames{oi};
                        baselineDS = baselineDS.addElement(bSig);
                        hasExpected = true;
                    end
                end

                if hasExpected
                    % Save the baseline Dataset to a MAT file
                    baselineMatPath = fullfile(outputDir, sprintf('baseline_scenario_%d.mat', sc));
                    baselineData = baselineDS; %#ok<NASGU>
                    save(baselineMatPath, 'baselineData');

                    % Add baseline criteria to the test case
                    bc = tc.addBaselineCriteria(baselineMatPath);
                    fprintf('  Scenario %d: Baseline criteria added from expected values\n', sc);
                end
            catch bcErr
                fprintf('  Scenario %d: Baseline criteria warning: %s\n', sc, bcErr.message);
            end

            fprintf('  TC %d created (input MAT → %s)\n', sc, matFilePath);
        end

        tf.saveToFile();
        fprintf('  Test file saved: %s  (%d test cases from %d scenarios)\n', testFilePath, numScenarios, numScenarios);

        results.phases.testgen.testFilePath  = testFilePath;
        results.phases.testgen.numTestCases  = numScenarios;
        results.phases.testgen.numScenarios  = numScenarios;
        results.phases.testgen.inputNames    = inputNames;
        results.phases.testgen.outputNames   = outputNames;
        results.phases.testgen.sheetNames    = sheetNames;

        %% ==================== PHASE 4: EXECUTION & COVERAGE ====================
        fprintf('\n==========================================================\n');
        fprintf('[Phase 4] Running test suite...\n');
        fprintf('==========================================================\n');

        tic;
        resultSet = ts.run();
        fprintf('  Execution completed in %.1fs.\n', toc);

        % ── Parse results and compare expected vs actual ──
        tsResults    = resultSet.getTestSuiteResults();
        caseOutcomes = {};
        allPassed    = true;

        % Storage for actual output values
        actualOutputs = cell(numScenarios, length(outputNames));

        % --- Hybrid approach: run sim() per scenario to extract actual outputs ---
        fprintf('  Extracting actual outputs via sim()...\n');
        for sc = 1:numScenarios
            matFilePath = fullfile(outputDir, sprintf('input_scenario_%d.mat', sc));
            if ~exist(matFilePath, 'file')
                fprintf('    Scenario %d: MAT file not found, skipping\n', sc);
                continue;
            end
            try
                loaded = load(matFilePath, 'inputData');
                simIn = Simulink.SimulationInput(modelName);
                simIn = simIn.setExternalInput(loaded.inputData);
                simOut = sim(simIn);

                % Determine the stop time to match output at correct time
                scenarioStopTime = str2double(simStopTime);

                % Try logsout first (has named signals)
                gotOutput = false;
                try
                    logsout = simOut.get('logsout');
                    if ~isempty(logsout) && isa(logsout, 'Simulink.SimulationData.Dataset')
                        for oi = 1:length(outputNames)
                            outName = outputNames{oi};
                            for ei = 1:logsout.numElements
                                elem = logsout.getElement(ei);
                                if strcmp(elem.Name, outName)
                                    sigTime = elem.Values.Time;
                                    sigData = double(elem.Values.Data);
                                    [~, tidx] = min(abs(sigTime - scenarioStopTime));
                                    actualOutputs{sc, oi} = sigData(tidx);
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
                                [~, tidx] = min(abs(sigTime - scenarioStopTime));
                                actualOutputs{sc, oi} = sigData(tidx);
                            end
                        end
                    catch, end
                end

                fprintf('    Scenario %d:', sc);
                for oi = 1:length(outputNames)
                    val = actualOutputs{sc, oi};
                    if isempty(val), val = NaN; end
                    fprintf(' %s=%g', outputNames{oi}, val);
                end
                fprintf('\n');
            catch simErr
                fprintf('    Scenario %d: sim() error: %s\n', sc, simErr.message);
            end
        end

        caseIdx = 0;
        for tsi = 1:length(tsResults)
            tcResults = tsResults(tsi).getTestCaseResults();
            for tci = 1:length(tcResults)
                caseIdx = caseIdx + 1;
                tcr       = tcResults(tci);
                tcNameStr = char(tcr.Name);
                simOutcome = char(string(tcr.Outcome));

                % Compare actual vs expected for each output
                outputMatch = true;
                for oi = 1:length(outputNames)
                    expVal = NaN;
                    if exist('expectedOutputs', 'var') && caseIdx <= size(expectedOutputs, 1)
                        expVal = expectedOutputs{caseIdx, oi};
                        if isempty(expVal), expVal = NaN; end
                    end
                    actVal = NaN;
                    if caseIdx <= size(actualOutputs, 1)
                        actVal = actualOutputs{caseIdx, oi};
                        if isempty(actVal), actVal = NaN; end
                    end
                    if ~isnan(expVal) && ~isnan(actVal)
                        if abs(actVal - expVal) > 1e-6
                            outputMatch = false;
                        end
                    end
                end

                % Final outcome: must pass Simulink test AND match expected outputs
                if outputMatch && strcmp(simOutcome, 'Passed')
                    finalOutcome = 'Passed';
                elseif strcmp(simOutcome, 'Disabled')
                    finalOutcome = 'Disabled';
                else
                    finalOutcome = 'Failed';
                    allPassed = false;
                end

                caseOutcomes{end+1, 1} = tcNameStr; %#ok<AGROW>
                caseOutcomes{end, 2}   = finalOutcome;
                caseOutcomes{end, 3}   = simOutcome;
                fprintf('  %s  →  %s (sim: %s, match: %d)\n', tcNameStr, finalOutcome, simOutcome, outputMatch);
            end
        end
        overallOutcome = 'Failed';
        if allPassed, overallOutcome = 'Passed'; end

        results.phases.execution.overallOutcome    = overallOutcome;
        results.phases.execution.caseOutcomes      = caseOutcomes;
        results.phases.execution.actualOutputs     = actualOutputs;
        results.phases.execution.expectedOutputs   = expectedOutputs;
        results.phases.execution.inputValuesSummary = inputValuesSummary;
        fprintf('  Overall: %s  (%d cases)\n', overallOutcome, size(caseOutcomes, 1));

        % ── Coverage report ──
        results.phases.coverage.available  = false;
        results.phases.coverage.reportPath = '';

        if hasSlCov
            fprintf('\n  Generating coverage report...\n');
            try
                covReportDir = fullfile(outputDir, 'coverage_report');
                if ~exist(covReportDir, 'dir'), mkdir(covReportDir); end

                covGenerated = false;
                for tsi = 1:length(tsResults)
                    tcResults = tsResults(tsi).getTestCaseResults();
                    for tci = 1:length(tcResults)
                        try
                            covResult = tcResults(tci).getCoverageResults();
                            if ~isempty(covResult)
                                reportFile = fullfile(covReportDir, 'coverage_report.html');
                                cvhtml(reportFile, covResult);
                                results.phases.coverage.available  = true;
                                results.phases.coverage.reportPath = reportFile;
                                covGenerated = true;
                                fprintf('  Coverage HTML: %s\n', reportFile);
                                break;
                            end
                        catch
                        end
                    end
                    if covGenerated, break; end
                end
                if ~covGenerated
                    fprintf('  No coverage data collected.\n');
                    results.phases.coverage.error = 'No coverage data collected';
                end
            catch covErr
                fprintf('  Coverage report failed: %s\n', covErr.message);
                results.phases.coverage.error = covErr.message;
            end
        else
            results.phases.coverage.error = 'Simulink Coverage license unavailable';
        end

        %% ==================== PHASE 5: EXPORT RESULTS TO EXCEL ====================
        fprintf('\n==========================================================\n');
        fprintf('[Phase 5] Exporting results to Excel...\n');
        fprintf('==========================================================\n');

        outputExcelPath = fullfile(outputDir, [modelName '_TestResults.xlsx']);
        fprintf('  Output Excel: %s\n', outputExcelPath);

        numCases = size(caseOutcomes, 1);

        % Build comprehensive results table
        tcNameCol     = cell(numCases, 1);
        scenarioCol   = cell(numCases, 1);
        statusCol     = cell(numCases, 1);
        simOutcomeCol = cell(numCases, 1);
        inputCols     = nan(numCases, length(inputNames));
        expectedCols  = nan(numCases, length(outputNames));
        actualCols    = nan(numCases, length(outputNames));

        for i = 1:numCases
            tcNameCol{i} = caseOutcomes{i, 1};
            if i <= numScenarios
                scenarioCol{i} = sheetNames{i};
            else
                scenarioCol{i} = 'N/A';
            end
            statusCol{i} = caseOutcomes{i, 2};
            simOutcomeCol{i} = caseOutcomes{i, 3};

            % Input values
            for ini = 1:length(inputNames)
                if exist('inputValuesSummary', 'var') && i <= size(inputValuesSummary, 1)
                    v = inputValuesSummary{i, ini};
                    if ~isempty(v), inputCols(i, ini) = v; end
                end
            end

            % Expected output values
            for oi = 1:length(outputNames)
                if exist('expectedOutputs', 'var') && i <= size(expectedOutputs, 1)
                    v = expectedOutputs{i, oi};
                    if ~isempty(v), expectedCols(i, oi) = v; end
                end
            end

            % Actual output values
            for oi = 1:length(outputNames)
                if i <= size(actualOutputs, 1)
                    v = actualOutputs{i, oi};
                    if ~isempty(v), actualCols(i, oi) = v; end
                end
            end
        end

        % Build the results table dynamically
        resultsT = table(tcNameCol, scenarioCol, 'VariableNames', {'TestCase', 'Scenario'});

        for ini = 1:length(inputNames)
            resultsT.(inputNames{ini}) = inputCols(:, ini);
        end
        for oi = 1:length(outputNames)
            resultsT.(['Expected_' outputNames{oi}]) = expectedCols(:, oi);
        end
        for oi = 1:length(outputNames)
            resultsT.(['Actual_' outputNames{oi}]) = actualCols(:, oi);
        end
        resultsT.SimulinkOutcome = simOutcomeCol;
        resultsT.Status = statusCol;

        writetable(resultsT, outputExcelPath, 'Sheet', 'Results');
        fprintf('  "Results" sheet written with %d test cases.\n', numCases);

        results.phases.export.excelPath = outputExcelPath;
        fprintf('  Results Excel: %s\n', outputExcelPath);

        %% ==================== CLEANUP ====================
        fprintf('\n==========================================================\n');
        fprintf('[Cleanup]\n');
        fprintf('==========================================================\n');

        if options.cleanupHarness
            try
                sltest.harness.delete(modelName, harnessName);
                fprintf('  Harness "%s" deleted.\n', harnessName);
            catch
                fprintf('  Warning: Could not delete harness.\n');
            end
        else
            fprintf('  Harness "%s" kept.\n', harnessName);
        end

        if options.cleanupTestFile
            try
                delete(testFilePath);
                fprintf('  Test file deleted.\n');
            catch
                fprintf('  Warning: Could not delete test file.\n');
            end
        else
            fprintf('  Test file kept: %s\n', testFilePath);
        end

        fprintf('  Cleanup complete.\n');

        results.success = true;
        fprintf('\n==========================================================\n');
        fprintf('=== TEST AUTOMATION COMPLETE — %s ===\n', overallOutcome);
        fprintf('==========================================================\n');

    catch ME
        results.success    = false;
        results.error      = ME.message;
        results.errorId    = ME.identifier;
        results.errorStack = arrayfun(@(s) sprintf('%s (line %d)', s.name, s.line), ...
            ME.stack, 'UniformOutput', false);
        fprintf('\n!!! ERROR: %s\n', ME.message);
        fprintf('    ID: %s\n', ME.identifier);
        for s = 1:length(ME.stack)
            fprintf('    at %s (line %d)\n', ME.stack(s).name, ME.stack(s).line);
        end
    end
end


%% ==================== HELPER: (SDI-based extraction is now inline) ====================
