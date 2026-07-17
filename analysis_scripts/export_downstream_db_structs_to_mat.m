%% Export BACPACS downstream SciDB records to MATLAB tables with struct columns
% This is the MATLAB-friendly analysis export. It reads derived tables from
% SciDB through the repository Python environment, preserves nested signal
% payloads as MATLAB structs, and saves one .mat file per analysis table.
%
% Each .mat contains:
%   bacpacs_table   - one row per DB analysis object, not one row per signal point
%   export_metadata - source DB/table/filter/path/run metadata
%
% Important shape:
%   CycleUnmatched: one row per gait cycle with struct columns such as
%     xsens_time_normalized
%     delsys_time_normalized
%     delsys_normalized_time_normalized
%     gaitrite_metrics
%   CycleMatched: one row per matched L/R cycle pair with struct columns such as
%     xsens_time_normalized
%     delsys_time_normalized
%     delsys_normalized_time_normalized
%     gaitrite_metrics

clearvars -except study;
clc;

%% SETTINGS
if ~exist("study", "var") || strlength(string(study)) == 0
    study = "R1";
end
filters = struct();
filters.participant_number = "";
filters.visit = "";
filters.test = "";
filters.condition = "";
filters.speed = "";
filters.trial = "";
filters.cycle = "";

%% PATHS
scriptDir = fileparts(mfilename("fullpath"));
repoRoot = fileparts(scriptDir);
pythonExe = fullfile(repoRoot, "BAKPACS_env", "python.exe");
helperScript = fullfile(scriptDir, "export_downstream_db_structs_for_matlab.py");
exportDir = fullfile(scriptDir, "exports", "matlab");
jsonDir = fullfile(exportDir, "json");

if ~isfile(pythonExe)
    error("BACPACS:MissingPython", "Could not find Python environment: %s", pythonExe);
end
if ~isfile(helperScript)
    error("BACPACS:MissingHelper", "Could not find helper script: %s", helperScript);
end
if ~exist(jsonDir, "dir")
    mkdir(jsonDir);
end

%% PULL STRUCTURED RECORDS FROM SCIDB
args = {
    char(pythonExe), ...
    char(helperScript), ...
    "--study", char(study), ...
    "--output-dir", char(jsonDir) ...
};
args = append_filter_arg(args, "participant-number", filters.participant_number);
args = append_filter_arg(args, "visit", filters.visit);
args = append_filter_arg(args, "test", filters.test);
args = append_filter_arg(args, "condition", filters.condition);
args = append_filter_arg(args, "speed", filters.speed);
args = append_filter_arg(args, "trial", filters.trial);
args = append_filter_arg(args, "cycle", filters.cycle);

cmd = join_command(args);
fprintf("Reading structured records from SciDB...\n%s\n", cmd);
[status, commandOutput] = system(cmd);
if status ~= 0
    error("BACPACS:StructuredExportFailed", "Python structured export failed:\n%s", commandOutput);
end

%% CONVERT JSON RECORDS TO MATLAB TABLES
tableSpecs = [
    struct("key", "trial", "json", "bacpacs_trial_structured.json", "mat", study + "_bacpacs_trial_structured.mat")
    struct("key", "cycle_unmatched", "json", "bacpacs_cycle_unmatched_structured.json", "mat", study + "_bacpacs_cycle_unmatched_structured.mat")
    struct("key", "cycle_matched", "json", "bacpacs_cycle_matched_structured.json", "mat", study + "_bacpacs_cycle_matched_structured.mat")
    struct("key", "visit", "json", "bacpacs_visit_structured.json", "mat", study + "_bacpacs_visit_structured.mat")
    struct("key", "analysis_issues", "json", "bacpacs_analysis_issues_structured.json", "mat", study + "_bacpacs_analysis_issues_structured.mat")
];

for idx = 1:numel(tableSpecs)
    spec = tableSpecs(idx);
    jsonPath = fullfile(jsonDir, spec.json);
    matPath = fullfile(exportDir, spec.mat);
    if ~isfile(jsonPath)
        warning("BACPACS:MissingStructuredJson", "Missing %s", jsonPath);
        continue;
    end

    rawText = fileread(jsonPath);
    records = jsondecode(rawText);
    bacpacs_table = records_to_table(records);

    export_metadata = struct();
    export_metadata.study = study;
    export_metadata.table_key = spec.key;
    export_metadata.json_path = string(jsonPath);
    export_metadata.mat_path = string(matPath);
    export_metadata.filters = filters;
    export_metadata.rows = height(bacpacs_table);
    export_metadata.columns = width(bacpacs_table);
    export_metadata.python_output = string(strtrim(commandOutput));
    export_metadata.exported_at = string(datetime("now", "Format", "yyyy-MM-dd HH:mm:ss"));

    fprintf("Saving %s: %d rows x %d columns -> %s\n", spec.key, height(bacpacs_table), width(bacpacs_table), matPath);
    save(matPath, "bacpacs_table", "export_metadata", "-v7.3");
end

fprintf("Done. Structured MATLAB exports are in %s\n", exportDir);

%% LOCAL HELPERS
function tbl = records_to_table(records)
    if isempty(records)
        tbl = table();
        return;
    end
    if isstruct(records)
        tbl = struct2table(records, "AsArray", true);
    else
        tbl = table(records);
    end
    tbl = standardize_struct_variables(tbl);
end

function tbl = standardize_struct_variables(tbl)
    names = tbl.Properties.VariableNames;
    for nameIdx = 1:numel(names)
        name = names{nameIdx};
        values = tbl.(name);
        if isstruct(values)
            tbl.(name) = num2cell(values);
        end
    end
end

function args = append_filter_arg(args, name, value)
    value = string(value);
    if strlength(value) == 0
        return;
    end
    args = [args, {"--" + name, char(value)}];
end

function cmd = join_command(args)
    quoted = cellfun(@quote_arg, args, "UniformOutput", false);
    cmd = strjoin(quoted, " ");
end

function quoted = quote_arg(value)
    value = char(string(value));
    value = strrep(value, '"', '\"');
    quoted = ['"' value '"'];
end