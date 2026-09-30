"""Select two didactic, real properties for the compliance walkthrough deck."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs" / "codigo_florestal_mt_inputs_completos.csv"
TARGET = ROOT / "qa" / "example_properties_for_compliance_deck.json"
FIELDS = [
    "priority_key", "input_file_type", "mun_geocodigo_norm", "MODULOS_FI",
    "area_ha_car", "radam_forest_ha", "radam_cerrado_ha", "cons_area_2000",
    "cons_area_2008", "veg_2000_ha", "veg_2008_ha", "req_teto_art12_ha",
    "req_piso_art68_ha", "rl_req_art67_ha", "rl_req_art68_ha",
    "rl_req_base_ha", "rl_exist_total_ha", "auas_post2008",
    "rl_adj_deficit_ha", "rl_restore_ha", "rl_compensate_ha", "app_req_ha",
    "app_preserved_ha", "app_consol_restore_ha", "app_restore_auas_ha",
    "app_restore_ha", "secondary_vegetation_raw_ha", "secondary_vegetation_ha",
    "rl_exist_total_with_secondary_ha", "rl_adj_deficit_with_secondary_ha",
    "calc_deficit_total_ha", "calc_deficit_total_with_secondary_ha",
]


def n(row, field):
    try:
        return float(row.get(field) or 0)
    except ValueError:
        return 0.0


def score(row, large):
    modules = n(row, "MODULOS_FI")
    area = n(row, "area_ha_car")
    deficit = n(row, "calc_deficit_total_ha")
    secondary = n(row, "secondary_vegetation_ha")
    target_modules = 6 if large else 2.5
    target_area = 650 if large else 180
    return abs(modules - target_modules) + abs(area - target_area) / 200 + abs(deficit - 60) / 100 - min(secondary, 50) / 100


candidates = {"large": [], "small": []}
with SOURCE.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
        modules = n(row, "MODULOS_FI")
        forest = n(row, "radam_forest_ha")
        cerrado = n(row, "radam_cerrado_ha")
        deficit = n(row, "calc_deficit_total_ha")
        secondary = n(row, "secondary_vegetation_ha")
        if forest <= 10 or cerrado <= 10 or deficit <= 10 or secondary <= 0:
            continue
        if modules > 4:
            candidates["large"].append(row)
        elif 0 < modules < 4:
            candidates["small"].append(row)

selected = {
    group: {field: min(rows, key=lambda row: score(row, group == "large")).get(field, "") for field in FIELDS}
    for group, rows in candidates.items()
}
TARGET.write_text(json.dumps(selected, indent=2), encoding="utf-8")
print(json.dumps(selected, indent=2))
