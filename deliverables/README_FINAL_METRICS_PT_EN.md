# Campos finais de RL, APP e vegetação secundária / Final RL, APP and secondary-vegetation fields

## Português

### Campos finais da linha de base

| Tema | Campo final | Interpretacao |
|---|---|---|
| RL | `rl_restore_ha` | Passivo final de Reserva Legal a recompor dentro do imóvel, em hectares. |
| RL | `rl_compensate_ha` | Parcela remanescente do passivo final de Reserva Legal destinada a compensação fora do imóvel, em hectares. |
| APP | `app_restore_ha` | Passivo final de APP a restaurar, em hectares. |
| Total | `calc_deficit_total_ha` | Passivo total da linha de base: `rl_adj_deficit_ha + app_restore_ha`. |

Portanto, sim: os campos finais continuam sendo `rl_restore_ha` e `rl_compensate_ha` para RL, e `app_restore_ha` para APP.

Os campos da linha de base estão nos arquivos `mato_grosso_forest_code_property_results.parquet` e `mato_grosso_forest_code_cattle_supplier_results.parquet`. Os arquivos com sufixo `_with_secondary_vegetation.parquet` mantêm esses campos da linha de base e acrescentam os campos do cenário de vegetação secundária.

`cons_area_2008` é a área consolidada de 2008 e permanece nos arquivos finais como insumo auditável para conferir a separação entre recomposição e compensação de RL. Nas fontes SIMCAR validada e digital, o campo vem da camada oficial `AREA_CONSOLIDADA`; no proxy, vem da camada específica `cons_area_2008`. O campo `cons_area_2000` permanece separado porque é usado no cenário/regra histórica de 2000 e não deve ser confundido com `cons_area_2008`.

### Como a vegetação secundária foi usada

A vegetação secundária é um cenário de sensibilidade separado e não substitui os resultados principais da linha de base.

1. `secondary_vegetation_ha` é associado espacialmente a cada imóvel.
2. Essa área é somada somente à RL florestal existente, formando `rl_exist_forest_with_secondary_ha`.
3. O modelo recalcula déficit, recomposição, compensação e excedente de RL nos campos terminados em `_with_secondary_ha`.
4. A vegetação secundária não aumenta APP existente e não altera `app_restore_ha`.
5. Se um imóvel não tem vegetação secundária mapeada (`secondary_vegetation_ha = 0`), os resultados do cenário são iguais aos da linha de base.

Assim, a vegetação secundária entra no cenário para aumentar a RL florestal existente e pode reduzir o passivo de RL ou aumentar o excedente de RL. Ela não é usada para aumentar APP existente.

## English

### Final baseline fields

| Topic | Final field | Interpretation |
|---|---|---|
| LR | `rl_restore_ha` | Final Legal Reserve liability to restore in situ, in hectares. |
| LR | `rl_compensate_ha` | Remaining final Legal Reserve liability eligible for off-property compensation, in hectares. |
| APP | `app_restore_ha` | Final APP restoration liability, in hectares. |
| Total | `calc_deficit_total_ha` | Total baseline liability: `rl_adj_deficit_ha + app_restore_ha`. |

Secondary vegetation is a separate sensitivity scenario. `secondary_vegetation_ha` is added only to existing forest LR, and the model recalculates LR deficit, restoration, compensation, surplus, and total liability in the `*_with_secondary_ha` fields. It does not increase existing APP or change `app_restore_ha`. Where no secondary vegetation is mapped, scenario and baseline results are identical.

Baseline fields are available in `mato_grosso_forest_code_property_results.parquet` and `mato_grosso_forest_code_cattle_supplier_results.parquet`. Files ending in `_with_secondary_vegetation.parquet` retain the baseline fields and add the secondary-vegetation scenario fields.

`cons_area_2008` is the 2008 consolidated-area input retained in final files so LR restoration and compensation can be audited. In validated and digital SIMCAR sources it comes from the official `AREA_CONSOLIDADA` layer; in the proxy source it comes from the dedicated `cons_area_2008` layer. `cons_area_2000` remains a separate input used by the historical 2000 rule/scenario and must not be treated as the same field.
