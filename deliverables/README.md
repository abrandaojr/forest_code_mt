# Final deliverables

- `01_excel/`: complete property-level input and compliance workbooks, split into 11 Excel files.
- `02_csv/`: complete property-level result table, split into four CSV files.
- `03_figures/`: final figures and maps.
- `04_presentation/`: final scientific dashboard presentation.
- `05_code/`: reproducible source-code package.
- `06_documentation/`: interactive field-lineage network and machine-readable JSON documentation.

This directory contains Forest Code deliverables only. Drafts, renderings, and superseded versions belong in `qa/` or `archive/`.

## Final compliance fields

- `rl_restore_ha`: final baseline Legal Reserve (RL) liability to restore in situ (ha).
- `rl_compensate_ha`: final baseline RL liability eligible for off-property compensation (ha).
- `app_restore_ha`: final baseline Permanent Preservation Area (APP) restoration liability (ha).
- `calc_deficit_total_ha`: final baseline total liability (`rl_adj_deficit_ha + app_restore_ha`).

Secondary vegetation is a separate sensitivity scenario. It is added only to existing forest RL and recalculated in the `*_with_secondary_ha` fields. It can reduce RL liability or increase RL surplus, but it does not increase existing APP and does not change `app_restore_ha`. Properties without mapped secondary vegetation have the same baseline and scenario results.

## Field lineage and export completeness

`06_documentation/forest_code_field_lineage_20260930.html` maps source layers, canonical fields, formulas, dependencies, and final outputs as an interactive network. The corresponding JSON contains the same graph and full schemas for automated review.

The final property exports retain `cons_area_2008` separately from `cons_area_2000`. The export schema is regression-tested by `tools/data_audit/audit_final_export_schema.py` so all required audit inputs remain present.
