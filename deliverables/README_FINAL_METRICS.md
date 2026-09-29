# Final LR, APP, and secondary-vegetation fields

## Final baseline fields

| Topic | Final field | Interpretation |
|---|---|---|
| LR | `rl_restore_ha` | Final Legal Reserve liability to restore in situ, in hectares. |
| LR | `rl_compensate_ha` | Remaining final Legal Reserve liability assigned to off-property compensation, in hectares. |
| APP | `app_restore_ha` | Final APP restoration liability, in hectares. |
| Total | `calc_deficit_total_ha` | Total baseline liability: `rl_adj_deficit_ha + app_restore_ha`. |

Baseline fields are available in `mato_grosso_forest_code_property_results.parquet` and `mato_grosso_forest_code_cattle_supplier_results.parquet`. Files ending in `_with_secondary_vegetation.parquet` retain the baseline fields and add the secondary-vegetation scenario fields.

`cons_area_2008` is the 2008 consolidated-area input retained in final files so LR restoration and compensation can be audited. In validated and digital SIMCAR sources it comes from the official `AREA_CONSOLIDADA` layer; in the proxy source it comes from the dedicated `cons_area_2008` layer. `cons_area_2000` remains a separate input used by the historical 2000 rule/scenario and must not be treated as the same field.

## Secondary vegetation

Secondary vegetation is a separate sensitivity scenario and does not replace the baseline results.

1. `secondary_vegetation_ha` is spatially assigned to each property.
2. This area is added only to existing forest LR, producing `rl_exist_forest_with_secondary_ha`.
3. The model recalculates LR deficit, restoration, compensation, surplus, and total liability in fields ending in `_with_secondary_ha`.
4. Secondary vegetation does not increase existing APP and does not change `app_restore_ha`.
5. When `secondary_vegetation_ha = 0`, scenario and baseline results are identical.
