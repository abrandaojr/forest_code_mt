from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("compliance", ROOT / "code" / "_11_forest_code_compliance.py")
assert SPEC and SPEC.loader
compliance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compliance)

CONFIG = {
    "rules": compliance.DEFAULT_RULES,
    "forest_label": "FLORESTA",
    "cerrado_label": "CERRADO",
    "mt_special": [],
}


def row(**overrides):
    base = {
        "priority_key": "p1",
        "area_ha_car": 100.0,
        "MODULOS_FI": 2.0,
        "mun_geocodigo": "0000000",
        "radam_FLORESTA_ha": 100.0,
        "radam_CERRADO_ha": 0.0,
        "radam_forest_nveg24_ha": 50.0,
        "radam_cerrado_nveg24_ha": 0.0,
        "cons_area_2000": 40.0,
        "cons_area_2008": 40.0,
        "auas_post2008": 5.0,
        "app": 0.0,
        "app_fnl_avn24": 0.0,
        "app_fnl_cs08": 0.0,
        "app_fnl_auas": 0.0,
        "appd_lte1mf_cs08": 0.0,
        "appd_1a2mf_cs08": 0.0,
        "appd_2a4mf_cs08": 0.0,
        "appd_4a10mf_cs08": 0.0,
        "appd_gt10mf_cs08": 0.0,
    }
    base.update(overrides)
    return base


def close(actual, expected, label):
    assert abs(float(actual) - expected) < 1e-9, f"{label}: {actual} != {expected}"


def main():
    small = compliance.compute_forest_code_metrics(pd.DataFrame([row()]), CONFIG).iloc[0]
    close(small.veg_2000_ha, 60, "2000 vegetation")
    close(small.veg_2008_ha, 60, "2008 vegetation")
    close(small.rl_req_base_ha, 60, "Art. 67 locked requirement")
    close(small.rl_restore_ha, 5, "post-2008 mandatory restoration")
    close(small.rl_compensate_ha, 5, "remaining compensation")

    surplus = compliance.compute_forest_code_metrics(
        pd.DataFrame([row(cons_area_2008=10, radam_forest_nveg24_ha=90)]), CONFIG
    ).iloc[0]
    close(surplus.rl_req_base_ha, 80, "Art. 67 ceiling")
    close(surplus.rl_surplus_total_ha, 10, "surplus preservation")

    large_legal = compliance.compute_forest_code_metrics(pd.DataFrame([row(MODULOS_FI=5)]), CONFIG).iloc[0]
    close(large_legal.rl_req_base_ha, 50, "Art. 68 legal trigger")
    large_illegal = compliance.compute_forest_code_metrics(
        pd.DataFrame([row(MODULOS_FI=5, cons_area_2000=60)]), CONFIG
    ).iloc[0]
    close(large_illegal.rl_req_base_ha, 80, "Art. 68 loss of benefit")

    app = compliance.compute_forest_code_metrics(
        pd.DataFrame([row(app=50, app_fnl_cs08=30, app_fnl_auas=20, appd_1a2mf_cs08=30)]), CONFIG
    ).iloc[0]
    close(app.app_consol_restore_ha, 10, "Art. 61-B cap on consolidated area")
    close(app.app_restore_ha, 30, "recent APP clearing added after cap")

    baseline = compliance.compute_forest_code_metrics(pd.DataFrame([row(MODULOS_FI=5, cons_area_2000=60)]), CONFIG)
    secondary = compliance.add_secondary_vegetation_scenarios(
        baseline, pd.DataFrame({"priority_key": ["p1"], "secondary_vegetation_ha": [20.0]})
    ).iloc[0]
    close(secondary.rl_adj_deficit_with_secondary_ha, 10, "secondary vegetation scenario")

    topology = compliance.compute_forest_code_metrics(
        pd.DataFrame([row(radam_forest_nveg24_ha=90, radam_cerrado_nveg24_ha=20)]), CONFIG
    ).iloc[0]
    close(topology.rl_exist_total_ha, 100, "current vegetation property-area ceiling")

    capped_secondary = compliance.add_secondary_vegetation_scenarios(
        pd.DataFrame([topology]),
        pd.DataFrame({"priority_key": ["p1"], "secondary_vegetation_ha": [500.0]}),
    ).iloc[0]
    close(capped_secondary.secondary_vegetation_ha, 0, "secondary vegetation available-space ceiling")
    close(capped_secondary.rl_exist_total_with_secondary_ha, 100, "combined vegetation property-area ceiling")
    assert capped_secondary.calc_deficit_total_with_secondary_ha <= capped_secondary.area_ha_car
    print("PASS: statutory cut-offs, Arts. 67/68, RL pathways, Art. 61-B, and secondary vegetation")


if __name__ == "__main__":
    main()
