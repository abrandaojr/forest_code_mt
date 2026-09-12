from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import _00_paths as paths
from _80_write_one_pager import add_lr_without_2000_rule


paths.set_env()

ROOT = paths.ROOT
TABLES = paths.TABLES
REPORTS = paths.REPORTS
TODAY = paths.RUN_DATE
HTML_OUT = REPORTS / f"forest_code_mt_noncompliance_pdf_summary_{TODAY}.html"
PDF_OUT = REPORTS / f"forest_code_mt_noncompliance_pdf_summary_{TODAY}.pdf"


def n(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def fmt(value: float, decimals: int = 0) -> str:
    if pd.isna(value):
        value = 0
    return f"{float(value):,.{decimals}f}"


def active_fc() -> pd.DataFrame:
    fc = pd.read_parquet(TABLES / f"forest_code_mt_priority_consolidated_{TODAY}.parquet")
    status = fc["SITUACAO"].astype(str).str.upper()
    fc = fc.loc[~status.str.contains("CANCELADO|INDEFERIDO|REJEIT", na=False)].copy()
    fc["mun_code"] = fc["mun_geocodigo"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    fc = fc[fc["mun_code"].str.startswith("51")].copy()
    return add_lr_without_2000_rule(fc)


def row(label: str, properties: float, hectares: float) -> dict[str, object]:
    properties = float(properties)
    hectares = float(hectares)
    return {
        "domain": label,
        "properties": properties,
        "hectares": hectares,
        "intensity": hectares / properties if properties else 0.0,
    }


def rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    fc = active_fc()
    gta = pd.read_parquet(TABLES / f"forest_code_gta_final_mt_{TODAY}.parquet")

    total = n(fc["calc_deficit_total_ha"])
    app = n(fc["app_restore_ha"])
    lr = n(fc["rl_adj_deficit_ha"])
    no2000 = n(fc["rl_adj_deficit_without_cons2000_ha"]) + app
    secondary = pd.read_parquet(TABLES / f"forest_code_mt_priority_consolidated_with_secondary_{TODAY}.parquet")
    secondary_deficit = n(secondary["calc_deficit_total_with_secondary_ha"])
    secondary_area = float(n(secondary["secondary_vegetation_ha"]).sum())

    core = [
        row("Total non-compliance", total.gt(0).sum(), total.sum()),
        row("APP non-compliance", app.gt(0).sum(), app.sum()),
        row("Legal Reserve non-compliance", lr.gt(0).sum(), lr.sum()),
        row("Regularization: restoration on farm", (n(fc["rl_restore_ha"]) + app).gt(0).sum(), (n(fc["rl_restore_ha"]) + app).sum()),
        row("Regularization: compensation off farm", n(fc["rl_compensate_ha"]).gt(0).sum(), n(fc["rl_compensate_ha"]).sum()),
        row("Scenario: without 2000 rule", no2000.gt(0).sum(), no2000.sum()),
        row("Sensitivity: non-compliance with secondary vegetation", secondary_deficit.gt(0).sum(), secondary_deficit.sum()),
    ]

    deficit = n(gta["calc_deficit_total_ha"])
    direct = n(gta["slaughter_or_export_cattle"]).gt(0)
    direct_gt50 = gta["direct_slaughter_gt50"].fillna(False).astype(bool)
    tier1 = gta["supplier_type"].astype(str).eq("Indirect supplier - Tier 1")
    tier2 = gta["supplier_type"].astype(str).eq("Indirect supplier - Tier 2+")

    supply = []
    for label, mask in [
        ("Direct suppliers | all direct", direct),
        ("Direct suppliers | >50% slaughter/export subgroup", direct & direct_gt50),
        ("Tier 1 suppliers", tier1),
        ("Tier 2+ suppliers", tier2),
    ]:
        bad = mask & deficit.gt(0)
        supply.append(row(label, bad.sum(), deficit.where(bad, 0).sum()))
    return core, supply


def table_html(items: list[dict[str, object]]) -> str:
    body = "\n".join(
        "<tr>"
        f"<td>{item['domain']}</td>"
        f"<td>{fmt(item['properties'])}</td>"
        f"<td>{fmt(item['hectares'])}</td>"
        f"<td>{fmt(item['intensity'], 2)}</td>"
        "</tr>"
        for item in items
    )
    return f"""
<table>
<thead><tr><th>Non-compliance domain</th><th>Non-compliant properties</th><th>Non-compliant hectares</th><th>Intensity, hectares/property</th></tr></thead>
<tbody>{body}</tbody>
</table>"""


def write_html(core: list[dict[str, object]], supply: list[dict[str, object]]) -> None:
    total = core[0]
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Forest Code Non-compliance Summary</title>
<style>
@page {{ size:A4; margin:18mm; }}
body {{ font-family:Arial, sans-serif; color:#111827; line-height:1.35; }}
h1 {{ font-size:24px; margin:0 0 8px; }}
h2 {{ font-size:16px; margin:18px 0 8px; }}
p {{ font-size:12px; margin:0 0 8px; }}
.lead {{ font-size:13px; color:#334155; }}
.cards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin:12px 0; }}
.card {{ border:1px solid #d9e0ea; padding:10px; }}
.label {{ font-size:10px; color:#5d6675; text-transform:uppercase; font-weight:bold; }}
.value {{ font-size:22px; font-weight:bold; margin-top:5px; }}
table {{ width:100%; border-collapse:collapse; font-size:11px; margin-top:6px; }}
th,td {{ border-bottom:1px solid #d9e0ea; padding:6px; text-align:right; }}
th:first-child,td:first-child {{ text-align:left; }}
th {{ background:#f1f5f9; }}
.note {{ font-size:10px; color:#5d6675; margin-top:10px; }}
</style>
</head>
<body>
<h1>Forest Code non-compliance summary</h1>
<p class="lead">Mato Grosso. The report centers on non-compliance: affected properties, affected hectares, and intensity per non-compliant property.</p>
<p class="lead">Intensity means the average non-compliant area among affected properties: non-compliant hectares divided by non-compliant properties.</p>
<div class="cards">
<div class="card"><div class="label">Non-compliant properties</div><div class="value">{fmt(total['properties'])}</div></div>
<div class="card"><div class="label">Non-compliant hectares</div><div class="value">{fmt(total['hectares'])}</div></div>
<div class="card"><div class="label">Intensity</div><div class="value">{fmt(total['intensity'], 2)}</div></div>
</div>
<h2>Core non-compliance</h2>
{table_html(core)}
<h2>Supply-chain non-compliance</h2>
<p>High-intensity direct suppliers are a subgroup of direct suppliers, defined by slaughter/export flows above 50% of total outflow.</p>
{table_html(supply)}
<p class="note">Intensity = non-compliant hectares / non-compliant properties. Source: Forest Code model outputs. CAR priority is validated, digital, then proxy. Numbers use US thousands separators.</p>
</body>
</html>"""
    HTML_OUT.write_text(html, encoding="utf-8")


def pdf_table(items: list[dict[str, object]]) -> Table:
    data = [["Non-compliance domain", "Properties", "Hectares", "Intensity"]]
    data += [[str(i["domain"]), fmt(i["properties"]), fmt(i["hectares"]), fmt(i["intensity"], 2)] for i in items]
    table = Table(data, colWidths=[2.75 * inch, 1.15 * inch, 1.35 * inch, 1.0 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e0ea")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def write_pdf(core: list[dict[str, object]], supply: list[dict[str, object]]) -> None:
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleTight", parent=styles["Title"], fontSize=20, leading=24, spaceAfter=8)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, leading=16, spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=13, spaceAfter=6)
    doc = SimpleDocTemplate(str(PDF_OUT), pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    total = core[0]
    story = [
        Paragraph("Forest Code non-compliance summary", title),
        Paragraph("Mato Grosso. The report centers on non-compliance: affected properties, affected hectares, and intensity per non-compliant property.", body),
        Paragraph("Intensity means the average non-compliant area among affected properties: non-compliant hectares divided by non-compliant properties.", body),
        pdf_table([total]),
        Spacer(1, 8),
        Paragraph("Core non-compliance", h2),
        pdf_table(core),
        Paragraph("Supply-chain non-compliance", h2),
        Paragraph("High-intensity direct suppliers are a subgroup of direct suppliers, defined by slaughter/export flows above 50% of total outflow.", body),
        pdf_table(supply),
        Spacer(1, 8),
        Paragraph("Intensity = non-compliant hectares / non-compliant properties. Source: Forest Code model outputs. CAR priority is validated, digital, then proxy. Numbers use US thousands separators.", body),
    ]
    doc.build(story)


def main() -> tuple[Path, Path]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    core, supply = rows()
    write_html(core, supply)
    write_pdf(core, supply)
    print(HTML_OUT)
    print(PDF_OUT)
    return HTML_OUT, PDF_OUT


if __name__ == "__main__":
    main()

