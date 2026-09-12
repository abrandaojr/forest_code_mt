from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    fc = load_module("_20_build_priority", "_20_build_priority.py")
    gta = load_module("_30_build_gta", "_30_build_gta.py")
    figs = load_module("_40_build_maps", "_40_build_maps.py")
    masson = load_module("_50_build_publication_tables", "_50_build_publication_tables.py")

    print("\n=== STEP 1/4: Forest Code priority consolidation ===")
    fc.main()

    print("\n=== STEP 2/4: GTA binary supplier join ===")
    gta.build_final_workbook()

    print("\n=== STEP 3/4: Final figures and maps ===")
    figs.build_figures_and_maps()

    print("\n=== STEP 4/4: Masson-style final tables and figures ===")
    masson.main()

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
