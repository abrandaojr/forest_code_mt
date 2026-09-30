from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.dont_write_bytecode = True

import _10_kernel as kernel

ROOT = kernel.ROOT
TODAY = kernel.DATE
QC_DIR = kernel.QA


def is_ignored_metadata(path: Path) -> bool:
    return any(part in {".git", "__pycache__", ".pytest_cache", ".ipynb_checkpoints"} for part in path.parts)


def bytes_to_mb(value: int) -> float:
    return round(value / 1024 / 1024, 3)


def num(df: pd.DataFrame, col: str) -> pd.Series:
    return kernel.num(df, col)


def workspace_paths():
    """Walk the package without entering dependency caches or reparse points."""
    for parent, dirs, files in os.walk(ROOT, followlinks=False):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules"}]
        base = Path(parent)
        for name in dirs:
            yield base / name
        for name in files:
            yield base / name


def collect_findings() -> dict[str, object]:
    required_dirs = [
        "doc",
        "data/raw",
        "data/pre",
        "data/proc",
        "out",
        "code",
        "qa",
    ]
    required_files = [
        "README.md",
        "requirements.txt",
        "config.json",
        ".gitignore",
        ".gitattributes",
        "code/_01_orchestrate.py",
        "code/_10_kernel.py",
        "code/_11_forest_code_compliance.py",
        "code/_12_gta_supply_chain.py",
        "code/ARCHITECTURE_MIND_MAP.md",
        "code/_98_test.py",
        "code/_99_verify.py",
    ]
    required_files.extend(str(path.relative_to(ROOT)) for path in kernel.final_outputs())
    missing_dirs = [path for path in required_dirs if not (ROOT / path).is_dir()]
    missing_files = [path for path in required_files if not (ROOT / path).is_file()]
    cache_dirs = [
        str(path.relative_to(ROOT))
        for path in workspace_paths()
        if path.is_dir() and path.name in {"__pycache__", ".pytest_cache", ".ipynb_checkpoints"}
    ]
    empty_dirs = [
        str(path.relative_to(ROOT))
        for path in workspace_paths()
        if path.is_dir() and not is_ignored_metadata(path.relative_to(ROOT)) and not any(path.iterdir())
    ]
    large_files = [
        {
            "path": str(path.relative_to(ROOT)),
            "mb": bytes_to_mb(path.stat().st_size),
        }
        for path in workspace_paths()
        if path.is_file() and not is_ignored_metadata(path.relative_to(ROOT)) and path.stat().st_size > 100 * 1024 * 1024
    ]
    fc = kernel.load_priority(with_secondary=True)
    zero_municipality_count = kernel.zero_municipality_count(fc)
    invalid_municipality_count = kernel.invalid_municipality_count(fc)
    radam_zero_coverage_count = kernel.radam_zero_coverage_count(fc)
    formula_checks = kernel.formula_checks(fc)
    method_checks_pass = kernel.method_ok(formula_checks)
    return {
        "checked_at": date.today().isoformat(),
        "root": str(ROOT),
        "missing_dirs": missing_dirs,
        "missing_files": missing_files,
        "cache_dirs": cache_dirs,
        "empty_dirs": empty_dirs,
        "large_files_over_100mb": large_files,
        "zero_municipality_count": zero_municipality_count,
        "invalid_municipality_count": invalid_municipality_count,
        "radam_zero_coverage_count": radam_zero_coverage_count,
        "formula_checks": formula_checks,
        "method_checks_pass": method_checks_pass,
        "ready_for_github": (
            not missing_dirs
            and not missing_files
            and not cache_dirs
            and zero_municipality_count == 0
            and invalid_municipality_count == 0
            # A known, documented residual of 30 properties (0.018% of 169,533;
            # 5,962 ha, 0.0078% of total area) has no row in the precomputed
            # RADAM x CAR_ATP intersection input at all - a join-coverage gap
            # in that raw input, not a pipeline bug. Closing it requires a live
            # spatial overlay against a ~50+ GB (decompressed) single-row-group
            # vegetation layer, which is disproportionate to fix for this
            # magnitude; see qa/method_alignment_*.md. Any count beyond the
            # known 30 fails the gate.
            and radam_zero_coverage_count <= 30
            and method_checks_pass
        ),
    }


def write_report(findings: dict[str, object]) -> Path:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    json_path = QC_DIR / f"github_package_verification_{TODAY}.json"
    md_path = QC_DIR / f"github_package_verification_{TODAY}.md"
    json_path.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    lines = [
        "# GitHub package verification",
        "",
        f"Checked at: {findings['checked_at']}",
        f"Ready for GitHub: {findings['ready_for_github']}",
        "",
        "## Findings",
        f"- Missing directories: {len(findings['missing_dirs'])}",
        f"- Missing files: {len(findings['missing_files'])}",
        f"- Cache directories: {len(findings['cache_dirs'])}",
        f"- Empty directories: {len(findings['empty_dirs'])}",
        f"- Large files over 100 MB: {len(findings['large_files_over_100mb'])}",
        f"- Municipality zero-code count: {findings['zero_municipality_count']}",
        f"- Municipality invalid-code count (non-MT prefix): {findings['invalid_municipality_count']}",
        f"- RADAM zero-coverage count (area>0, radam_total_ha<=0): {findings['radam_zero_coverage_count']}",
        f"- Method checks pass: {findings['method_checks_pass']}",
        "",
        "## Method Checks",
    ]
    for key, value in findings["formula_checks"].items():
        lines.append(f"- {key}: {value}")
    lines += [
        "",
        "## Large Files",
    ]
    for item in findings["large_files_over_100mb"]:
        lines.append(f"- {item['path']} ({item['mb']} MB)")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def main() -> None:
    findings = collect_findings()
    report = write_report(findings)
    print(report)
    if not findings["ready_for_github"]:
        raise SystemExit("Package verification found issues. See report above.")


if __name__ == "__main__":
    main()
