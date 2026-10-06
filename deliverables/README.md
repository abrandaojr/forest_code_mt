# Final Forest Code package — Mato Grosso

Release date: **2026-10-06**. Population: **155,547 unique rural properties**.

Use the numbered folders in this order:

1. `01_excel/`: final summary workbook plus ten property-level mega-table workbooks. Every compliance formula and its source inputs are visible at property level.
2. `02_csv/`: final property-level results, split into three CSV files.
3. `02_csv_raw/`: complete raw and derived input mega table, split into thirteen CSV files.
4. `03_figures/`: final statewide figures and maps.
5. `04_presentation/`: final results deck and six GTA-linked worked examples (Validated, Digital, and Proxy; up to and above four fiscal modules).
6. `05_code/`: reproducible source-code release.
7. `06_documentation/`: field lineage, formula definitions, and machine-readable documentation.

## Final compliance fields

- `rl_restore_ha`: final baseline Legal Reserve (RL) liability to restore in situ (ha).
- `rl_compensate_ha`: final baseline RL liability eligible for off-property compensation (ha).
- `app_restore_ha`: final baseline Permanent Preservation Area (APP) restoration liability (ha).
- `calc_deficit_total_ha`: final baseline total liability (`rl_adj_deficit_ha + app_restore_ha`).

Native secondary vegetation is included in remaining native vegetation in the sensitivity scenario and is capped so total native vegetation never exceeds property area.

## Field lineage and export completeness

The documentation maps source layers, canonical fields, formulas, dependencies, and final outputs. The corresponding JSON contains the same lineage and full schemas for automated review.

The final property exports retain `cons_area_2008` separately from `cons_area_2000`. The export schema is regression-tested by `tools/data_audit/audit_final_export_schema.py` so all required audit inputs remain present.

## Passed safeguards

- `cons_area_2000 <= cons_area_2008 <= area_ha_car` for every assessed property.
- APP native vegetation, pre-2008 clearing, and post-2008 clearing are mutually exclusive and sum to mapped APP area.
- Compliance components and native vegetation totals cannot exceed property area.
- Post-2008 clearing is never assigned outside the area consolidated by 2008.
- All statewide APP intersections were processed with 25 × 25 km tiles.

Twenty-eight properties have no mapped RADAM formation coverage. They are retained and explicitly flagged as a source-coverage limitation; this is not interpreted as observed zero native vegetation.

Superseded editions are excluded from the published Google Drive and GitHub release.
