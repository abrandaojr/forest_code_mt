# Final LR, APP, and secondary-vegetation fields

## Final data folder

`02_FINAL_DATA` is organized by format:

1. `01_PARQUET`: one baseline file and two secondary-scenario parts.
2. `02_CSV/01_FINAL_RESULTS`: four parts containing the final consolidated results.
3. `02_CSV/02_RAW_INPUTS`: fifteen parts containing 169,533 properties and all 638 traceable raw/source fields.
4. `03_EXCEL`: eleven workbooks containing the same 169,533 properties, raw fields, and 77 live compliance formulas per property.

Files are split only to remain below the Google Drive upload limit. Read the numbered parts in order; headers are repeated in every CSV part.

## Final baseline fields

| Topic | Final field | Interpretation |
|---|---|---|
| LR | `rl_restore_ha` | Final Legal Reserve liability to restore in situ, in hectares. |
| LR | `rl_compensate_ha` | Remaining final Legal Reserve liability assigned to off-property compensation, in hectares. |
| APP | `app_restore_ha` | Final APP restoration liability, in hectares. |
| Total | `calc_deficit_total_ha` | Total baseline liability: `min(rl_adj_deficit_ha + app_restore_ha, area_ha_car)`. |

Baseline fields are available in `mato_grosso_forest_code_property_results.parquet` and `mato_grosso_forest_code_cattle_supplier_results.parquet`. Files ending in `_with_secondary_vegetation.parquet` retain the baseline fields and add the secondary-vegetation scenario fields.

`cons_area_2008` is the 2008 consolidated-area input retained in final files so LR restoration and compensation can be audited. In validated and digital SIMCAR sources it comes from the official `AREA_CONSOLIDADA` layer; in the proxy source it comes from the dedicated `cons_area_2008` layer. `cons_area_2000` remains a separate input used by the historical 2000 rule/scenario and must not be treated as the same field.

## Secondary vegetation

Secondary vegetation is a separate sensitivity scenario and does not replace the baseline results.

1. `secondary_vegetation_raw_ha` retains the spatially assigned source value for auditing.
2. `secondary_vegetation_ha` is the effective amount included in remaining vegetation: `min(secondary_vegetation_raw_ha, max(area_ha_car - rl_exist_total_ha, 0))`.
3. The effective area is added to existing forest LR, and `rl_exist_total_with_secondary_ha` can never exceed `area_ha_car`.
4. The model recalculates LR deficit, restoration, compensation, surplus, and total liability in fields ending in `_with_secondary_ha`.
5. Secondary vegetation does not increase existing APP and does not change `app_restore_ha`.
6. Baseline and secondary-scenario aggregate liabilities are capped at `area_ha_car`.
7. When `secondary_vegetation_ha = 0`, scenario and baseline results are identical.
