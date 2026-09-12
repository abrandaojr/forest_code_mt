from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.dont_write_bytecode = True

import _10_kernel as kernel

ROOT = kernel.ROOT
TODAY = kernel.DATE


def fail(message: str) -> None:
    raise AssertionError(message)


def test_python_compiles() -> None:
    scripts = list((ROOT / "code").rglob("*.py"))
    for script in scripts:
        if "__pycache__" in script.parts:
            continue
        source = script.read_text(encoding="utf-8")
        compile(source, str(script), "exec")
    print(f"OK python compile: {len(scripts)} scripts")


def test_core_outputs() -> None:
    required = kernel.final_outputs()
    missing = [path for path in required if not path.exists()]
    if missing:
        fail("Missing required outputs:\n" + "\n".join(str(path) for path in missing))
    print(f"OK required outputs: {len(required)}")


def test_calculation_invariants() -> None:
    fc = kernel.load_priority()
    checks = kernel.formula_checks(fc)
    if not kernel.method_ok(checks):
        fail(f"Forest Code formula mismatch: {checks}")
    zero_count = kernel.zero_municipality_count(fc)
    if zero_count:
        fail(f"Municipality zero-code findings remain: {zero_count}")
    invalid_count = kernel.invalid_municipality_count(fc)
    if invalid_count:
        fail(f"Municipality invalid-code (non-MT prefix) findings remain: {invalid_count}")
    # A documented residual of <=30 properties (0.018%) is missing entirely
    # from the precomputed RADAM x CAR_ATP intersection input (see
    # qa/method_alignment_*.md) - a raw-input coverage gap, not a pipeline
    # bug. Any count beyond that known residual fails the test.
    radam_gap = kernel.radam_zero_coverage_count(fc)
    if radam_gap > 30:
        fail(f"RADAM zero-coverage findings exceed the known 30-property residual: {radam_gap}")
    print("OK calculation invariants")


def test_municipality_code_field_priority() -> None:
    """Regression test for a real bug: derive_municipality_code() ranked the
    composite `car_code` field (PROTOCOLO + '-' + CODIGO_CAR, e.g.
    "MT250844/2024-MT-5105176-...") above the dedicated `MUNICIPIO_` geocode
    field. When CODIGO_CAR/CAR_FEDERA are both absent (a registration still
    awaiting analysis, with car_code truncated to just "MT<protocol>/<year>-")
    the digit-extraction fallback concatenated the protocol number with the
    year into a bogus but valid-looking 7-digit code, silently misassigning
    the property to a different (real) municipality elsewhere in Brazil
    instead of using the correct, available MUNICIPIO_ value. Caught by
    inspecting out/table/forest_code_mt_priority_consolidated_*.parquet
    directly: 13,985 of 169,533 properties (across all three CAR sources,
    since digital/validated preprocessing reuse this same function) had a
    mun_geocodigo not starting with '51' (Mato Grosso's IBGE state prefix);
    6,361 of those were active (non-cancelled) properties silently dropped
    from every '51'-filtered headline report, totaling 2.71M ha."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_10_preprocess_proxy", ROOT / "code" / "preprocess" / "_10_preprocess_proxy.py"
    )
    proxy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proxy)

    df = pd.DataFrame({
        "CODIGO_CAR": ["0"],
        "CAR_FEDERA": [pd.NA],
        "car_code": ["MT162438/2019-"],
        "NUMEROESTA": [pd.NA],
        "MUNICIPIO_": ["5106315"],
    })
    out = proxy.derive_municipality_code(df)
    if out.iloc[0] != "5106315":
        fail(f"MUNICIPIO_ must win over a malformed car_code: got {out.iloc[0]!r}, expected '5106315'")
    print("OK municipality code field priority (MUNICIPIO_ over malformed car_code)")


def test_radam_forest_cerrado_classification() -> None:
    """Regression test for the audit fix in _11_forest_code_compliance.py:
    forest/cerrado RADAM columns must be matched exactly (radam_<LABEL>_ha),
    not by substring, and unclassified area must be surfaced, not silently
    dropped from the RL basis without a trace."""
    import _11_forest_code_compliance as fcc

    df = pd.DataFrame({
        "area_ha_car": [100.0, 50.0, 10.0],
        "MODULOS_FI": [1, 1, 1],
        "mun_geocodigo": ["0", "0", "0"],
        "radam_FLORESTA_ha": [40.0, 20.0, 0.0],
        "radam_CERRADO_ha": [30.0, 0.0, 0.0],
        "radam__ha": [5.0, 0.0, 0.0],
        "radam_NONE_ha": [0.0, 0.0, 3.0],
        # Hypothetical future ecotone category: must NOT be counted as both
        # forest and cerrado (that would double-count it under a substring match).
        "radam_CERRADO_FLORESTA_ha": [0.0, 8.0, 0.0],
    })
    config = {"forest_label": "FLORESTA", "cerrado_label": "CERRADO"}
    out = fcc.compute_forest_code_metrics(df, config)

    if out.loc[0, "radam_forest_ha_raw"] != 40.0 or out.loc[0, "radam_cerrado_ha_raw"] != 30.0:
        fail(f"exact-match forest/cerrado sums wrong: {out.loc[0, ['radam_forest_ha_raw', 'radam_cerrado_ha_raw']].to_dict()}")
    if out.loc[1, "radam_forest_ha_raw"] != 20.0 or out.loc[1, "radam_cerrado_ha_raw"] != 0.0:
        fail(f"ecotone-like column must not be double-counted into forest/cerrado: {out.loc[1].to_dict()}")
    if out.loc[1, "radam_unclassified_ha_raw"] != 8.0 or not bool(out.loc[1, "radam_unclassified_flag"]):
        fail(f"ecotone-like column must be surfaced as unclassified: {out.loc[1].to_dict()}")
    if out.loc[0, "radam_unclassified_ha_raw"] != 5.0 or not bool(out.loc[0, "radam_unclassified_flag"]):
        fail(f"blank-category area must be surfaced as unclassified: {out.loc[0].to_dict()}")
    if out.loc[2, "radam_unclassified_ha_raw"] != 3.0 or not bool(out.loc[2, "radam_unclassified_flag"]):
        fail(f"null-category ('None') area must be surfaced as unclassified: {out.loc[2].to_dict()}")
    if bool(out.loc[2, "radam_unclassified_flag"]) and out.loc[2, "radam_total_ha"] != 0.0:
        fail("unclassified-only row must not silently gain forest/cerrado area")
    print("OK radam forest/cerrado classification (exact match + unclassified surfaced)")


def test_radam_unclassified_ignores_derived_columns() -> None:
    """Regression test for a real bug caught by running the full pipeline once
    the audit fix landed: a live run of code/preprocess/_10_preprocess_proxy.py
    passed compute_forest_code_metrics a `df` that already carried its own
    output columns (radam_forest_ha, radam_cerrado_ha, radam_total_ha) plus the
    ARL-allocation columns (radam_*_nveg24_ha) - all of which also match the
    radam_*_ha pattern. Without this guard they get re-summed into
    radam_unclassified_ha_raw, inflating it from ~11.8k ha to ~84M ha across
    168k of 176k properties in the real production data."""
    import _11_forest_code_compliance as fcc

    df = pd.DataFrame({
        "area_ha_car": [100.0],
        "MODULOS_FI": [1],
        "mun_geocodigo": ["0"],
        "radam_FLORESTA_ha": [40.0],
        "radam_CERRADO_ha": [30.0],
        "radam__ha": [5.0],
        # Pre-existing derived columns that must be ignored as "unclassified" input.
        "radam_forest_ha": [999.0],
        "radam_cerrado_ha": [999.0],
        "radam_total_ha": [1998.0],
        "radam_forest_nveg24_ha": [999.0],
        "radam_cerrado_nveg24_ha": [999.0],
        "radam_total_nveg24_ha": [1998.0],
    })
    out = fcc.compute_forest_code_metrics(df, {"forest_label": "FLORESTA", "cerrado_label": "CERRADO"})
    if out.loc[0, "radam_unclassified_ha_raw"] != 5.0:
        fail(f"derived radam_*_ha columns leaked into unclassified total: got {out.loc[0, 'radam_unclassified_ha_raw']}, expected 5.0")
    if out.loc[0, "radam_forest_ha"] != 40.0 or out.loc[0, "radam_cerrado_ha"] != 30.0:
        fail(f"pre-existing derived columns corrupted the recomputed forest/cerrado values: {out.loc[0].to_dict()}")
    print("OK radam unclassified total ignores pre-existing derived radam_*_ha columns")


def test_interactive_html() -> None:
    html = (kernel.REPORTS / f"forest_code_mt_interactive_one_pager_{TODAY}.html").read_text(encoding="utf-8")
    required = [
        'id="lang"',
        'id="share"',
        'id="slides"',
        "scroll-snap-type:y",
        "scroll-snap-align:start",
        "Mobile carousel",
        "Carrossel móvel",
        "Source hierarchy",
        "Hierarquia das fontes",
        "Supply chain",
        "Cadeia de fornecedores",
        "navigator.share",
        "wa.me",
        "Forest Code Diagnostic",
        "Diagnóstico do Código Florestal",
        "-webkit-text-size-adjust",
        "100svh",
    ]
    missing = [item for item in required if item not in html]
    if missing:
        fail("Interactive HTML missing required elements: " + ", ".join(missing))
    banned = ["https://unpkg.com/leaflet", "L.map", "L.geoJSON", "FeatureCollection", 'id="map"', "topicPairs"]
    found_banned = [item for item in banned if item in html]
    if found_banned:
        fail("Vertical carousel HTML contains heavy map payload: " + ", ".join(found_banned))
    app_script = html.split("var DATA = ", 1)[1]
    modern_js = ["=>", "?.", "const ", "let ", "async", "await", "Object.entries"]
    found_modern = [item for item in modern_js if item in app_script]
    if found_modern:
        fail("Interactive HTML app script uses iPhone-risky JS: " + ", ".join(found_modern))
    print("OK vertical carousel HTML")


def main() -> None:
    try:
        test_python_compiles()
        test_core_outputs()
        test_calculation_invariants()
        test_radam_forest_cerrado_classification()
        test_radam_unclassified_ignores_derived_columns()
        test_municipality_code_field_priority()
        test_interactive_html()
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        raise
    print("All tests passed.")


if __name__ == "__main__":
    main()

