%% Export BACPACS SciDB table to a MATLAB .mat file
% Run this script from MATLAB. Edit only the SETTINGS block unless you are
% changing the export behavior. The output .mat file contains:
%   bacpacs_table   - MATLAB table loaded from the SciDB export
%   export_metadata - study/table/filter/path/run metadata

clearvars;
clc;

%% SETTINGS
study = "R1";
tableName = "R1DelsysProcessed";
exportLayout = "analysis";  % "analysis" gives one row per frame/sample across trials; "records" keeps one row per DB record.

% Leave a filter as "" to include all values for that field.
filters = struct();
filters.participant_number = "001";
filters.visit = "BL";
filters.test = "";
filters.condition = "";
filters.speed = "";
filters.trial = "";
filters.cycle = "";

%% PATHS
scriptDir = fileparts(mfilename("fullpath"));
repoRoot = fileparts(scriptDir);
pythonExe = fullfile(repoRoot, "BAKPACS_env", "python.exe");
helperScript = fullfile(scriptDir, "export_scidb_table_for_matlab.py");
exportDir = fullfile(scriptDir, "exports");

if ~isfile(pythonExe)
    error("BACPACS:MissingPython", "Could not find Python environment: %s", pythonExe);
end
if ~isfile(helperScript)
    error("BACPACS:MissingHelper", "Could not find export helper: %s", helperScript);
end
if ~exist(exportDir, "dir")
    mkdir(exportDir);
end

%% EXPORT FROM SCIDB TO CSV
timestamp = string(datetime("now", "Format", "yyyyMMdd_HHmmss"));
baseName = study + "_" + tableName + "_" + exportLayout + "_" + timestamp;
csvPath = fullfile(exportDir, baseName + ".csv");
matPath = fullfile(exportDir, baseName + ".mat");

args = {
    char(pythonExe), ...
    char(helperScript), ...
    "--study", char(study), ...
    "--table", char(tableName), ...
    "--output", char(csvPath), ...
    "--layout", char(exportLayout) ...
};
args = append_filter_arg(args, "participant-number", filters.participant_number);
args = append_filter_arg(args, "visit", filters.visit);
args = append_filter_arg(args, "test", filters.test);
args = append_filter_arg(args, "condition", filters.condition);
args = append_filter_arg(args, "speed", filters.speed);
args = append_filter_arg(args, "trial", filters.trial);
args = append_filter_arg(args, "cycle", filters.cycle);

cmd = join_command(args);
fprintf("Running export helper...\n%s\n", cmd);
[status, commandOutput] = system(cmd);
if status ~= 0
    error("BACPACS:ExportFailed", "Python export failed:\n%s", commandOutput);
end

%% LOAD CSV AS MATLAB TABLE AND SAVE .MAT
opts = detectImportOptions(csvPath, "TextType", "string");
textColumns = intersect(["participant_number", "visit", "test", "condition", "speed", "cycle", "__record_id", "file_path"], string(opts.VariableNames));
if ~isempty(textColumns)
    opts = setvartype(opts, cellstr(textColumns), "string");
end
bacpacs_table = readtable(csvPath, opts);

export_metadata = struct();
export_metadata.study = study;
export_metadata.table_name = tableName;
export_metadata.layout = exportLayout;
export_metadata.filters = filters;
export_metadata.csv_path = string(csvPath);
export_metadata.mat_path = string(matPath);
export_metadata.python_output = string(strtrim(commandOutput));
export_metadata.exported_at = string(datetime("now", "Format", "yyyy-MM-dd HH:mm:ss"));

save(matPath, "bacpacs_table", "export_metadata");
fprintf("Saved %d rows x %d columns to:\n%s\n", height(bacpacs_table), width(bacpacs_table), matPath);

%% LOCAL HELPERS
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
    quoted = ['"', value, '"'];
end