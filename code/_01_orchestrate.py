from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import _00_paths as paths


ROOT = Path(__file__).resolve().parents[1]
FINAL_CODE = ROOT / "code"
SUMMARY_CODE = ROOT / "code" / "preprocess"


def configure_environment() -> None:
    paths.set_env()
    for path in [FINAL_CODE, SUMMARY_CODE, paths.CODE]:
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    print(f"workers: {paths.workers()} of {paths.os.cpu_count() or 1}")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_preprocess() -> None:
    steps = [
        ("SIMCAR proxy preprocessing", SUMMARY_CODE / "_10_preprocess_proxy.py", "run_fc_summary_mt"),
        ("SIMCAR digital preprocessing", SUMMARY_CODE / "_11_preprocess_digital.py", "run_fc_summary_mt_digital"),
        ("SIMCAR validated preprocessing", SUMMARY_CODE / "_12_preprocess_validated.py", "run_fc_summary_mt_validado"),
    ]
    for label, path, function_name in steps:
        print(f"\n=== {label} ===")
        module = load_module(path.stem, path)
        getattr(module, function_name)()


def run_core_pipeline() -> None:
    print("\n=== Final Forest Code pipeline ===")
    load_module("_60_run_pipeline", FINAL_CODE / "_60_run_pipeline.py").main()


def run_reports() -> None:
    print("\n=== Raw-data provenance ===")
    load_module("_70_write_provenance", FINAL_CODE / "_70_write_provenance.py").main()
    print("\n=== Final report and one-pagers ===")
    load_module("_80_write_one_pager", FINAL_CODE / "_80_write_one_pager.py").build_png()
    load_module("_80_write_one_pager_pt", FINAL_CODE / "_80_write_one_pager.py").build_png("pt")
    load_module("_85_write_interactive_one_pager", FINAL_CODE / "_85_write_interactive_one_pager.py").main()
    load_module("_90_write_report", FINAL_CODE / "_90_write_report.py").main()


def main() -> None:
    parser = argparse.ArgumentParser(description="Orchestrate the portable Forest Code package.")
    parser.add_argument(
        "--stage",
        choices=["preprocess", "core", "reports", "all"],
        default="reports",
        help="Execution stage. Use 'all' for a full rebuild.",
    )
    args = parser.parse_args()
    configure_environment()
    if args.stage in {"preprocess", "all"}:
        run_preprocess()
    if args.stage in {"core", "all"}:
        run_core_pipeline()
    if args.stage in {"reports", "all"}:
        run_reports()
    print("\nDone.")


if __name__ == "__main__":
    main()
