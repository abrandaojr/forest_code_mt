# Mato Grosso Forest Code Model

Portable workflow for property-level Forest Code compliance in Mato Grosso.

The Excel model with raw input columns and live compliance formulas is documented in `code/excel_property_level/`. Final deliverables are stored in the permanent [Forest Code MT final-results folder](https://drive.google.com/drive/folders/12ttP2ry23WF2Jq_GXVdXX4dGBpJMq544).

## Start here — order of importance

1. `01_START_HERE_fields_formulas_and_results.html` — read the final results, fields, formulas, legal rules, and output destinations.
2. `02_FINAL_DATA/` — use the final property-level datasets.
3. `03_FINAL_PROPERTY_PRIORITY_TABLES_20260818.xlsx` — review property prioritization results.
4. `04_FINAL_GTA_RESULTS_20260818.xlsx` — review cattle supply-chain results.
5. `05_FINAL_PUBLICATION_TABLES_AND_FIGURES_20260818.xlsx` — use publication-ready tables and figure data.
6. `06_FINAL_TECHNICAL_REPORT_20260818.docx` — read the full technical interpretation.
7. `07_FINAL_FIGURES/` — access final figures and maps.
8. `08_FINAL_REPRODUCIBLE_CODE/` — reproduce the workflow.
9. `09_TECHNICAL_LINEAGE_DATA.json` — inspect machine-readable field lineage.
10. `10_README_FINAL_METRICS.md` — consult the concise metric definitions.

## Method

Input priority:

1. SIMCAR validated
2. SIMCAR digital
3. SIMCAR proxy

All non-property spatial layers should be tiled at 25 x 25 km before spatial joins.

## Final compliance fields

- `rl_restore_ha`: final baseline Legal Reserve (RL) liability to be restored in situ (ha).
- `rl_compensate_ha`: final baseline RL liability eligible for off-property compensation (ha).
- `app_restore_ha`: final baseline Permanent Preservation Area (APP) restoration liability (ha).
- `calc_deficit_total_ha`: final baseline total liability, equal to `rl_adj_deficit_ha + app_restore_ha`.

Secondary vegetation is reported as a separate sensitivity scenario, not as part of the baseline fields above. `secondary_vegetation_ha` is added only to existing forest RL, producing the `*_with_secondary_ha` fields. It can reduce RL restoration or compensation and increase RL surplus. It does not increase existing APP and does not change `app_restore_ha`. For properties without mapped secondary vegetation, the secondary-vegetation scenario equals the baseline.

## Structure

- `deliverables/01_excel`: final property-level Excel workbooks
- `deliverables/02_csv`: complete property-level CSV results
- `deliverables/03_figures`: final figures and maps
- `deliverables/04_presentation`: final scientific dashboard presentation
- `deliverables/05_code`: reproducible code package
- `code`: workflow, tests, helpers
- `data`: raw, preprocessed, processed data
- `doc`: method references
- `out/table`: data products
- `out/fig`: figures
- `out/report`: generated technical reports and one-pagers
- `out/qgis`: QGIS project
- `qa/presentation`: presentation previews and visual QA
- `qa`: data and model audit files
- `scientific_presentation`: presentation build source
- `tools`: audit, Excel, and project utilities
- `archive`: superseded delivery packages and temporary legacy files

## Run

```powershell
conda run -n geo python code/_01_orchestrate.py --stage reports
conda run -n geo python code/_98_test.py
conda run -n geo python code/_99_verify.py
```

Full run:

```powershell
conda run -n geo python code/_01_orchestrate.py --stage all
```

Use Git LFS for large files.

Default compute use: 80% of logical CPUs. Override with `FCM_WORKERS`.

