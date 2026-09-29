# Mato Grosso Forest Code — Final Reproducible Code

This code package reproduces the final property-level results, cattle-supplier results, publication tables, maps, and spatial-input audit.

## Contents

- `config.json`: project-relative input and output paths.
- `requirements.txt`: Python dependencies.
- `code/preprocess/`: SIMCAR proxy, digital, and validated preprocessing, including the corrected statewide RADAM intersection logic.
- `code/_20_build_priority.py`: property-source prioritization.
- `code/_30_build_gta.py`: cattle-supplier classification and join.
- `code/_40_build_maps.py`: final municipal maps and analytical figures.
- `code/_50_build_publication_tables.py`: final publication tables and secondary-vegetation scenario.
- `code/_16_audit_spatial_inputs.py`: mapped inventory and coverage audit of spatial inputs.
- `code/_17_verify_self_contained_project.py`: verifies that analytical inputs remain inside the local project.
- `code/_60_run_pipeline.py`: runs the final analytical pipeline.
- `code/_98_test.py` and `code/_99_verify.py`: calculation and package validation.

## Run

Install `requirements.txt`, then run `python code/_01_orchestrate.py --stage all` from the project root. Input data must remain under `data/`; raw inputs are intentionally not duplicated in Google Drive.

## Final fields and secondary-vegetation scenario

The final baseline compliance fields are:

- `rl_restore_ha`: Legal Reserve (RL) liability to restore in situ (ha).
- `rl_compensate_ha`: remaining RL liability eligible for off-property compensation (ha).
- `app_restore_ha`: Permanent Preservation Area (APP) restoration liability (ha).
- `calc_deficit_total_ha`: total baseline liability (`rl_adj_deficit_ha + app_restore_ha`).

Secondary vegetation is a separate sensitivity scenario. The model spatially assigns `secondary_vegetation_ha` to properties and adds it only to existing forest RL (`rl_exist_forest_with_secondary_ha`). It then recalculates RL deficit, restoration, compensation, surplus, and total liability in fields ending in `_with_secondary_ha`. It does not increase existing APP or change `app_restore_ha`. When `secondary_vegetation_ha = 0`, the scenario results equal the baseline results.

The baseline fields are stored in the property and cattle-supplier result files without the `_with_secondary_vegetation` suffix. The corresponding files with that suffix retain the baseline fields and add the sensitivity-scenario fields.
