from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[2]
source = root / "tools" / "audit_and_build"

groups = {
    "paper": {
        "build_surgical_paper.py", "build_tracked_commented_paper.py",
        "convert_paper_tables.py", "list_paper_media.py", "paper_metrics.py",
        "revise_paper.py", "scratch_dump.py", "_dump_papers.py",
        "_inspect_word_user.py",
    },
    "excel": {
        "_build_complete_formula_excel.py", "_build_complete_input_csv.py",
        "_build_full_property_excel.py", "_check_csv_values.py",
        "_compare_excel_python.py", "_inspect_parity_row.py", "_recalc_sample.ps1",
        "_recompute_current_code.py", "_verify_complete_excels.py",
        "_verify_full_property_excel.py",
    },
    "data_audit": {
        "_audit_formula_inputs.py", "_audit_property_sources.py", "_audit_raw_join.py",
        "_compare_current_python_module.py", "_test_python_module_import.py",
        "_verify_all_compliance.py",
    },
    "project": {"_reorganize_project.py"},
}

for group, names in groups.items():
    destination = root / "tools" / group
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        src = source / name
        if src.exists():
            shutil.move(str(src), str(destination / name))

print("Utility scripts organized")
