"""Command-line interface for the BACPACS multimodal pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from Modality_Pipelines.common.lightweight_registry import get_stage_registry, get_supported_studies

OPERATIONAL_COMMANDS = {"validate", "register", "process", "status", "analyses", "analyze"}


def _add_common_filters(parser: argparse.ArgumentParser, *, include_modality: bool = True) -> None:
    parser.add_argument("--participant-number", "--participant", dest="participant_number")
    parser.add_argument("--visit")
    if include_modality:
        parser.add_argument("--modality")
    parser.add_argument("--test")
    parser.add_argument("--condition")
    parser.add_argument("--speed")
    parser.add_argument("--trial")


def _add_study(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--study", choices=get_supported_studies(), help="Study namespace to operate on.")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bacpacs",
        usage="bacpacs <command> [options]",
        description="BACPACS multimodal ambulation pipeline CLI.",
        epilog=(
            "Examples:\n"
            "  bacpacs doctor\n"
            "  bacpacs validate --study R2\n"
            "  bacpacs register --study R2 --dry-run\n"
            "  bacpacs process --study R2 --modality all\n"
            "  bacpacs status --study R2"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the Streamlit control panel.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    subparsers.add_parser("studies", help="List configured studies.")

    doctor = subparsers.add_parser("doctor", help="Check this computer's network/repo environment.")
    doctor.add_argument("--study", choices=get_supported_studies(), help="Optional study namespace to check.")
    doctor.add_argument("--performance", action="store_true", help="Time shared-drive and SciStack database probes for machine-to-machine comparison.")

    gui = subparsers.add_parser("gui", help="Launch the Streamlit control panel.")
    gui.add_argument("streamlit_args", nargs=argparse.REMAINDER, help="Extra arguments passed to Streamlit.")

    validate = subparsers.add_parser("validate", usage="bacpacs validate --study {R1,R2} [filters] [options]", help="Dry-run validate raw-file layout and filenames.")
    _add_study(validate)
    _add_common_filters(validate)
    validate.add_argument("--root", help="Override subject-data root for this validation run.")
    validate.add_argument("--limit", type=_positive_int, default=20, help="Rows to summarize from the validation manifest.")
    validate.add_argument("--output", help="Optional CSV path for the full validation manifest.")

    register = subparsers.add_parser("register", usage="bacpacs register --study {R1,R2} [filters] [--dry-run] [options]", help="Register valid raw files in study RawFile tables.")
    _add_study(register)
    _add_common_filters(register)
    register.add_argument("--root", help="Override subject-data root for this registration run.")
    register.add_argument("--dry-run", action="store_true", help="Count records without writing to SciDB.")
    register.add_argument("--database-path", help="Override the SciDB/DuckDB database path.")
    register.add_argument("--update-existing", action="store_true", help="Reserved for future idempotent updates.")

    process = subparsers.add_parser("process", usage="bacpacs process --study {R1,R2} --modality <modality|all> [filters] [options]", help="Run first-pass modality processing.")
    _add_study(process)
    _add_common_filters(process, include_modality=False)
    process.add_argument("--modality", default="all", help="Modality to process, or 'all'.")
    process.add_argument("--dry-run", action="store_true", help="Ask SciStack to plan processing without saving outputs.")
    process.add_argument("--database-path", help="Override the SciDB/DuckDB database path.")
    process.add_argument("--overwrite", action="store_true", help="Recompute even if outputs already exist.")
    process.add_argument("--include-processed", action="store_true", help="Do not skip already computed records.")

    status = subparsers.add_parser("status", usage="bacpacs status --study {R1,R2}", help="Show study table/stage registry.")
    _add_study(status)

    analyses = subparsers.add_parser("analyses", usage="bacpacs analyses --study {R1,R2} [--modality <modality>]", help="List registered downstream analyses.")
    _add_study(analyses)
    analyses.add_argument("--modality", help="Filter analyses by modality.")

    analyze = subparsers.add_parser("analyze", usage="bacpacs analyze --study {R1,R2} <build-trial|build-cycles|finalize-visit|normalize-cycles|build-matched|export|build-all> [filters] [options]", help="Run downstream analysis table stages.")
    _add_study(analyze)
    _add_common_filters(analyze, include_modality=False)
    analyze.add_argument("analysis_command", nargs="?", help="Derived analysis stage to run, or omit when using --analysis for registry analyses.")
    analyze.add_argument("--analysis", help="Legacy registry analysis key to run.")
    analyze.add_argument("--dry-run", action="store_true", help="Ask SciStack to plan analysis without saving outputs.")
    analyze.add_argument("--database-path", help="Override the SciDB/DuckDB database path.")
    analyze.add_argument("--output-dir", help="Output directory for derived analysis exports.")
    analyze.add_argument("--overwrite", action="store_true", help="Recompute even if outputs already exist.")
    analyze.add_argument("--include-processed", action="store_true", help="Do not skip already computed records.")

    return parser


def _require_study(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.command in OPERATIONAL_COMMANDS and not getattr(args, "study", None):
        parser.error(f"'{args.command}' requires --study R1 or --study R2")


def _filter_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "participant_number": getattr(args, "participant_number", None),
        "visit": getattr(args, "visit", None),
        "modality": getattr(args, "modality", None),
        "test": getattr(args, "test", None),
        "condition": getattr(args, "condition", None),
        "speed": getattr(args, "speed", None),
        "trial": getattr(args, "trial", None),
    }


def _clean_filters(filters: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in filters.items() if value is not None}


def _print_mapping(title: str, rows: dict[str, Any]) -> None:
    print(title)
    for key, value in rows.items():
        print(f"  {key}: {value}")


def _print_progress(message: str) -> float:
    print(message, flush=True)
    return time.perf_counter()


def _print_elapsed(start_time: float, label: str = "Done") -> None:
    elapsed = time.perf_counter() - start_time
    print(f"{label} in {elapsed:.1f}s", flush=True)


def _cmd_studies(args: argparse.Namespace) -> int:
    from Modality_Pipelines.common.study_config import load_study_config

    print("Configured studies")
    for study in get_supported_studies():
        config = load_study_config(study)
        print(f"  {config.study}: {config.project_name}")
        print(f"      subject_data_root: {config.subject_data_root}")
        print(f"      database_path: {config.database_path}")
    return 0


def _format_path_status(path: Path) -> str:
    return "ok" if path.exists() else "missing"


def _time_probe(label: str, fn) -> None:
    start_time = time.perf_counter()
    try:
        detail = fn()
    except Exception as exc:  # pragma: no cover - diagnostic output path
        elapsed = time.perf_counter() - start_time
        print(f"  {label}: error in {elapsed:.2f}s ({exc.__class__.__name__}: {exc})")
        return
    elapsed = time.perf_counter() - start_time
    print(f"  {label}: {detail} in {elapsed:.2f}s")


def _count_first_dirs(root: Path, pattern: str, limit: int = 25) -> str:
    count = 0
    for candidate in root.glob(pattern):
        if candidate.is_dir():
            count += 1
        if count >= limit:
            break
    return f"found {count} participant folder(s), capped at {limit}"


def _count_first_children(root: Path, limit: int = 25) -> str:
    count = 0
    for _ in root.iterdir():
        count += 1
        if count >= limit:
            break
    return f"listed {count} item(s), capped at {limit}"


def _print_performance_probes(studies: list[str]) -> None:
    from Modality_Pipelines.common.common_config import configure_scistack_database
    from Modality_Pipelines.common.study_config import load_study_config

    print("Performance probes")
    print("Compare these timings on both computers. Large gaps usually indicate mapped-drive, VPN, antivirus, or SMB caching differences.")
    for study in studies:
        config = load_study_config(study)
        print(f"{config.study}: {config.project_name}")
        _time_probe("subject root exists", lambda config=config: "ok" if config.subject_data_root.exists() else "missing")
        if config.subject_data_root.exists():
            _time_probe(
                "enumerate participant folders",
                lambda config=config: _count_first_dirs(config.subject_data_root, config.participant_glob),
            )
        _time_probe("database path exists", lambda config=config: "ok" if config.database_path.exists() else "missing")
        if config.database_path.parent.exists():
            _time_probe("database folder listing", lambda config=config: _count_first_children(config.database_path.parent))
        if config.database_path.exists():
            _time_probe(
                "SciStack configure/list variables",
                lambda config=config: f"{len(configure_scistack_database(study_config=config).list_variables())} variable type(s)",
            )


def _cmd_doctor(args: argparse.Namespace) -> int:
    from Modality_Pipelines.common.study_config import load_study_config

    repo_root = Path(__file__).resolve().parents[1]
    env_candidates = [
        repo_root / "BACPACS_env" / "python.exe",
        repo_root / "BACPACS_env" / "Scripts" / "python.exe",
        repo_root / "BAKPACS_env" / "python.exe",
        repo_root / "BAKPACS_env" / "Scripts" / "python.exe",
    ]
    env_python = next((candidate for candidate in env_candidates if candidate.exists()), None)

    print("BACPACS environment check")
    print(f"python: {sys.executable}")
    print(f"repo_root: {repo_root} [{_format_path_status(repo_root)}]")
    if env_python:
        print(f"repo_env_python: {env_python} [ok]")
    else:
        print("repo_env_python: missing")

    studies = [args.study] if args.study else get_supported_studies()
    for study in studies:
        config = load_study_config(study)
        database_parent = config.database_path.parent
        print(f"{config.study}: {config.project_name}")
        print(f"  subject_data_root: {config.subject_data_root} [{_format_path_status(config.subject_data_root)}]")
        print(f"  database_path: {config.database_path} [{_format_path_status(config.database_path)}]")
        print(f"  database_folder: {database_parent} [{_format_path_status(database_parent)}]")
    if args.performance:
        _print_performance_probes(list(studies))
    return 0


def _cmd_gui(args: argparse.Namespace) -> int:
    app_path = Path(__file__).resolve().parent / "control_panel" / "app.py"
    command = [sys.executable, "-m", "streamlit", "run", str(app_path), *getattr(args, "streamlit_args", [])]
    print("Launching BACPACS control panel...")
    print(" ".join(str(part) for part in command))
    return subprocess.call(command)


def _display_manifest_value(value: Any, default: str = "?") -> Any:
    if value is None or value != value:
        return default
    return value


def _print_manifest_summary(df: Any, limit: int) -> None:
    if not limit:
        print("Manifest row summaries suppressed by --limit 0.")
        return

    rows = df.head(limit)
    print(f"Manifest rows (showing {len(rows)} of {len(df)}):")
    for display_index, (_, row) in enumerate(rows.iterrows(), start=1):
        file_name = row.get("file_name") or "<missing file_name>"
        status = row.get("status") or "<missing status>"
        folder = row.get("file_path") or ""
        participant = _display_manifest_value(row.get("participant_number"))
        visit = _display_manifest_value(row.get("visit"))
        modality = _display_manifest_value(row.get("modality"))
        test = _display_manifest_value(row.get("test"))
        condition = _display_manifest_value(row.get("condition"))
        speed = _display_manifest_value(row.get("speed"))
        trial = _display_manifest_value(row.get("trial"))
        issues = row.get("issues") or "none"
        print(f"  {display_index}. {status}: {file_name}")
        print(f"     identity: participant={participant}, visit={visit}, modality={modality}, test={test}, condition={condition}, speed={speed}, trial={trial}")
        print(f"     issues: {issues}")
        if folder:
            print(f"     path: {folder}")
    remaining = len(df) - len(rows)
    if remaining > 0:
        print(f"  ... {remaining} additional row(s) hidden. Use --limit N or --output manifest.csv for full details.")


def _cmd_validate(args: argparse.Namespace) -> int:
    from Modality_Pipelines.common.manifest import validate_study_files

    filters = _clean_filters(_filter_kwargs(args))
    start_time = _print_progress(f"Validating raw files for study={args.study}...")
    df = validate_study_files(study=args.study, root=args.root, **filters)
    _print_elapsed(start_time, "Validation complete")
    print(f"Validation manifest: {len(df)} row(s)")
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"Full manifest written to: {output_path}")
    if df.empty:
        return 0
    status_counts = df["status"].value_counts(dropna=False).to_dict()
    _print_mapping("Status counts", status_counts)
    _print_manifest_summary(df, args.limit)
    return 0 if not (df["status"] == "review").any() else 2

def _cmd_register(args: argparse.Namespace) -> int:
    from Modality_Pipelines.common.manifest import register_raw_files

    filters = _clean_filters(_filter_kwargs(args))
    start_time = _print_progress(
        f"Preparing raw-file registration for study={args.study} ({'dry-run' if args.dry_run else 'write'})..."
    )
    counts = register_raw_files(
        study=args.study,
        root=args.root,
        dry_run=args.dry_run,
        update_existing=args.update_existing,
        database_path=args.database_path,
        **filters,
    )
    _print_elapsed(start_time, "Registration step complete")
    mode = "dry-run" if args.dry_run else "write"
    print(f"Raw-file registration ({mode})")
    _print_mapping("Counts", counts)
    return 0


def _cmd_process(args: argparse.Namespace) -> int:
    from Modality_Pipelines.common.processing import run_modality_processing

    filters = _clean_filters(_filter_kwargs(args))
    modality = filters.pop("modality", args.modality)
    start_time = _print_progress(
        f"{'Planning' if args.dry_run else 'Running'} processing for study={args.study}, modality={modality}..."
    )
    result = run_modality_processing(
        study=args.study,
        modality=modality,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        unprocessed_only=not args.include_processed,
        database_path=args.database_path,
        **filters,
    )
    _print_elapsed(start_time, "Processing step complete")
    print(f"Processing dispatched for study={args.study}, modality={modality}")
    print(result)
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    from Modality_Pipelines.common.study_config import load_study_config

    config = load_study_config(args.study)
    print(f"{config.study}: {config.project_name}")
    print(f"subject_data_root: {config.subject_data_root}")
    print(f"database_path: {config.database_path}")
    print("Registered table stages")
    for modality, stages in get_stage_registry(args.study).items():
        print(f"  {modality}")
        print(f"      raw_file: {stages['raw_file']}")
        print(f"      processed: {', '.join(stages['processed'])}")
    return 0


def _cmd_analyses(args: argparse.Namespace) -> int:
    from Modality_Pipelines.common.analysis_registry import list_available_analyses

    rows = list_available_analyses(study=args.study, modality=args.modality)
    if not rows:
        print("No downstream analyses are registered.")
        return 0
    print(f"Available analyses for {args.study}")
    for row in rows:
        outputs = ", ".join(row.get("output_tables", []))
        print(f"  {row['name']} [{row['modality']}] {row.get('input_table', '?')} -> {outputs}")
        if row.get("description"):
            print(f"      {row['description']}")
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    filters = _clean_filters(_filter_kwargs(args))
    filters.pop("modality", None)
    command = getattr(args, "analysis_command", None)
    derived_commands = {
        "build-trial": "build_trial_analysis",
        "build-cycles": "build_cycle_unmatched",
        "finalize-visit": "finalize_visit_summary",
        "normalize-cycles": "normalize_cycles_to_visit",
        "build-matched": "build_cycle_matched",
        "export": "export_analysis_tables",
        "build-all": "build_all",
    }

    if command in derived_commands:
        from Modality_Pipelines.common import downstream_analysis

        fn = getattr(downstream_analysis, derived_commands[command])
        kwargs = {"study": args.study, "database_path": args.database_path, **filters}
        if command in {"export", "build-all"}:
            kwargs["output_dir"] = args.output_dir
        start_time = _print_progress(f"Running downstream analysis stage {command} for study={args.study}...")
        try:
            result = fn(**kwargs)
        except downstream_analysis.AnalysisPreconditionError as exc:
            print(f"Analysis precondition failed: {exc}", file=sys.stderr)
            return 2
        _print_elapsed(start_time, "Analysis stage complete")
        print(result)
        return 0

    if command and not args.analysis:
        valid = ", ".join(sorted(derived_commands))
        print(f"Unknown analysis command {command!r}. Expected one of: {valid}; or use --analysis <registry-key>.", file=sys.stderr)
        return 2

    if not args.analysis:
        print("analyze requires a derived stage name or --analysis <registry-key>.", file=sys.stderr)
        return 2

    from Modality_Pipelines.common.analysis_registry import run_registered_analysis

    start_time = _print_progress(
        f"{'Planning' if args.dry_run else 'Running'} analysis for study={args.study}, analysis={args.analysis}..."
    )
    result = run_registered_analysis(
        study=args.study,
        analysis=args.analysis,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        unprocessed_only=not args.include_processed,
        database_path=args.database_path,
        **filters,
    )
    _print_elapsed(start_time, "Analysis step complete")
    print(f"Analysis dispatched for study={args.study}, analysis={args.analysis}")
    print(result)
    return 0

def dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    _require_study(args, parser)
    handlers = {
        "studies": _cmd_studies,
        "doctor": _cmd_doctor,
        "gui": _cmd_gui,
        "validate": _cmd_validate,
        "register": _cmd_register,
        "process": _cmd_process,
        "status": _cmd_status,
        "analyses": _cmd_analyses,
        "analyze": _cmd_analyze,
    }
    if args.command is None:
        parser.print_help()
        return 0
    return handlers[args.command](args)


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


def main(argv: list[str] | None = None) -> int:
    _configure_console_encoding()
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch(args, parser)


if __name__ == "__main__":
    raise SystemExit(main())
