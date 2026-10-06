import csv
import html
import os
import re
import zipfile
from collections import Counter

SOURCE = r'out\table\forest_code_mt_priority_consolidated_with_secondary_20260818.csv'
PART = int(os.environ.get('FC_PART', '1'))
START = 0 if PART == 1 else 84338
END = 84338 if PART == 1 else 168676
DEST = rf'outputs\codigo_florestal_mt_propriedades_parte_{PART}.xlsx'
FORMULA_KEEP = {
    'rl_adj_deficit_ha', 'rl_restore_ha', 'rl_compensate_ha',
    'app_gross_deficit_ha', 'app_restore_ha',
    'calc_gross_deficit_total_ha', 'calc_deficit_total_ha',
    'rl_adj_deficit_with_secondary_ha', 'rl_restore_with_secondary_ha',
    'rl_compensate_with_secondary_ha',
    'calc_gross_deficit_total_with_secondary_ha',
    'calc_deficit_total_with_secondary_ha',
    'compliant_baseline', 'compliant_with_secondary',
    'secondary_changes_to_compliant',
}
NUM = re.compile(r'^-?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?$')

def col(i):
    s = ''
    while i:
        i, x = divmod(i - 1, 26)
        s = chr(65 + x) + s
    return s

def xml(s):
    return html.escape(s, quote=False)

with open(SOURCE, encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    headers = next(reader)
    ix = {h: col(i + 1) for i, h in enumerate(headers)}
    def c(name, row): return f'{ix[name]}{row}'
    def fml(name, row):
        v = lambda n: c(n, row)
        formulas = {
            'radam_total_ha': lambda: f'{v("radam_forest_ha")}+{v("radam_cerrado_ha")}',
            'rl_req_uncapped_forest_ha': lambda: f'{v("radam_forest_ha")}*0.8',
            'rl_req_uncapped_cerrado_ha': lambda: f'{v("radam_cerrado_ha")}*0.35',
            'rl_req_uncapped_total_ha': lambda: f'{v("rl_req_uncapped_forest_ha")}+{v("rl_req_uncapped_cerrado_ha")}',
            'rl_req_forest_ha': lambda: f'IF({v("rl_req_uncapped_total_ha")}=0,0,MIN({v("rl_req_uncapped_total_ha")},MAX({v("area_ha_car")}-{v("cons_area_2000")},0))*{v("rl_req_uncapped_forest_ha")}/{v("rl_req_uncapped_total_ha")})',
            'rl_req_cerrado_ha': lambda: f'IF({v("rl_req_uncapped_total_ha")}=0,0,MIN({v("rl_req_uncapped_total_ha")},MAX({v("area_ha_car")}-{v("cons_area_2000")},0))*{v("rl_req_uncapped_cerrado_ha")}/{v("rl_req_uncapped_total_ha")})',
            'rl_req_total_ha': lambda: f'{v("rl_req_forest_ha")}+{v("rl_req_cerrado_ha")}',
            'rl_exist_total_ha': lambda: f'{v("rl_exist_forest_ha")}+{v("rl_exist_cerrado_ha")}',
            'rl_gross_deficit_forest_ha': lambda: f'MAX({v("rl_req_forest_ha")}-{v("rl_exist_forest_ha")},0)',
            'rl_gross_deficit_cerrado_ha': lambda: f'MAX({v("rl_req_cerrado_ha")}-{v("rl_exist_cerrado_ha")},0)',
            'rl_gross_deficit_ha': lambda: f'{v("rl_gross_deficit_forest_ha")}+{v("rl_gross_deficit_cerrado_ha")}',
            'rl_surplus_forest_ha': lambda: f'MAX({v("rl_exist_forest_ha")}-{v("rl_req_forest_ha")},0)',
            'rl_surplus_cerrado_ha': lambda: f'MAX({v("rl_exist_cerrado_ha")}-{v("rl_req_cerrado_ha")},0)',
            'rl_surplus_total_ha': lambda: f'{v("rl_surplus_forest_ha")}+{v("rl_surplus_cerrado_ha")}',
            'art67_small_prop': lambda: f'{v("MODULOS_FI")}<=4',
            'rl_adj_deficit_forest_ha': lambda: f'IF({v("art67_small_prop")},0,IF({v("art68_exempt_forest")},MAX({v("rl_req_pre2000_forest_ha")}-{v("rl_exist_forest_ha")},0),IF({v("mt_special_mun")},MAX({v("rl_req_mt_forest_ha")}-{v("rl_exist_forest_ha")},0),MAX({v("rl_req_forest_ha")}-{v("rl_exist_forest_ha")},0))))',
            'rl_adj_deficit_cerrado_ha': lambda: f'IF({v("art67_small_prop")},0,IF({v("art68_exempt_cerrado")},MAX({v("rl_req_pre2000_cerrado_ha")}-{v("rl_exist_cerrado_ha")},0),MAX({v("rl_req_cerrado_ha")}-{v("rl_exist_cerrado_ha")},0)))',
            'rl_adj_deficit_ha': lambda: f'{v("rl_adj_deficit_forest_ha")}+{v("rl_adj_deficit_cerrado_ha")}',
            'rl_post2008_ha': lambda: f'MIN({v("auas_post2008")},MAX({v("area_ha_car")}-{v("cons_area_2000")},0))',
            'rl_restore_ha': lambda: f'MIN({v("rl_post2008_ha")},{v("rl_adj_deficit_ha")})',
            'rl_compensate_ha': lambda: f'MAX({v("rl_adj_deficit_ha")}-{v("rl_restore_ha")},0)',
            'app_req_ha': lambda: v('app'),
            'app_gross_deficit_ha': lambda: f'MAX({v("app_req_ha")}-{v("app_preserved_ha")},0)',
            'app_consol_restore_ha': lambda: f'MIN({v("app_replant_raw_ha")},{v("app_consolidated_ha")},{v("app_gross_deficit_ha")})',
            'app_restore_ha': lambda: f'MIN({v("app_consol_restore_ha")}+{v("app_restore_auas_ha")},{v("app_gross_deficit_ha")},IF(ISNUMBER({v("app_cap_ha")}),{v("app_cap_ha")},1E+99))',
            'calc_gross_deficit_total_ha': lambda: f'MIN({v("rl_adj_deficit_ha")}+{v("app_gross_deficit_ha")},{v("area_ha_car")})',
            'calc_deficit_total_ha': lambda: f'MIN({v("rl_adj_deficit_ha")}+{v("app_restore_ha")},{v("area_ha_car")})',
            'rl_exist_forest_with_secondary_ha': lambda: f'{v("rl_exist_forest_ha")}+{v("secondary_vegetation_ha")}',
            'rl_gross_deficit_forest_with_secondary_ha': lambda: f'MAX({v("rl_req_forest_ha")}-{v("rl_exist_forest_with_secondary_ha")},0)',
            'rl_surplus_forest_with_secondary_ha': lambda: f'MAX({v("rl_exist_forest_with_secondary_ha")}-{v("rl_req_forest_ha")},0)',
            'rl_gross_deficit_with_secondary_ha': lambda: f'{v("rl_gross_deficit_forest_with_secondary_ha")}+{v("rl_gross_deficit_cerrado_ha")}',
            'rl_surplus_with_secondary_ha': lambda: f'{v("rl_surplus_forest_with_secondary_ha")}+{v("rl_surplus_cerrado_ha")}',
            'rl_adj_deficit_forest_with_secondary_ha': lambda: f'IF({v("art67_small_prop")},0,IF(AND({v("rl_exist_forest_with_secondary_ha")}>={v("rl_req_pre2000_forest_ha")},{v("radam_forest_ha")}>0),0,IF({v("mt_special_mun")},MAX({v("rl_req_mt_forest_ha")}-{v("rl_exist_forest_with_secondary_ha")},0),{v("rl_gross_deficit_forest_with_secondary_ha")})))',
            'rl_adj_deficit_cerrado_with_secondary_ha': lambda: v('rl_adj_deficit_cerrado_ha'),
            'rl_adj_deficit_with_secondary_ha': lambda: f'{v("rl_adj_deficit_forest_with_secondary_ha")}+{v("rl_adj_deficit_cerrado_with_secondary_ha")}',
            'rl_restore_with_secondary_ha': lambda: f'MIN({v("rl_adj_deficit_with_secondary_ha")},{v("rl_post2008_ha")})',
            'rl_compensate_with_secondary_ha': lambda: f'MAX({v("rl_adj_deficit_with_secondary_ha")}-{v("rl_restore_with_secondary_ha")},0)',
            'calc_gross_deficit_total_with_secondary_ha': lambda: f'MIN({v("rl_adj_deficit_with_secondary_ha")}+{v("app_gross_deficit_ha")},{v("area_ha_car")})',
            'calc_deficit_total_with_secondary_ha': lambda: f'MIN({v("rl_adj_deficit_with_secondary_ha")}+{v("app_restore_ha")},{v("area_ha_car")})',
            'secondary_deficit_reduction_ha': lambda: f'MAX({v("calc_deficit_total_ha")}-{v("calc_deficit_total_with_secondary_ha")},0)',
            'compliant_baseline': lambda: f'{v("calc_deficit_total_ha")}<=0',
            'compliant_with_secondary': lambda: f'{v("calc_deficit_total_with_secondary_ha")}<=0',
            'secondary_changes_to_compliant': lambda: f'AND(NOT({v("compliant_baseline")}),{v("compliant_with_secondary")})',
        }
        return formulas[name]() if name in FORMULA_KEEP else None

    keys = set()
    dupes = 0
    source_counts = Counter()
    formula_count = 0
    row_count = 0
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    with zipfile.ZipFile(DEST, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3, allowZip64=True) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="PROPRIEDADES" sheetId="1" r:id="rId1"/></sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>')
        z.writestr('xl/styles.xml', '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="10"/><name val="Aptos"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="10"/><name val="Aptos"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF17324D"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="1" fillId="1" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs></styleSheet>')
        with z.open('xl/worksheets/sheet1.xml', 'w', force_zip64=True) as out:
            def w(s): out.write(s.encode('utf-8'))
            w('<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" state="frozen" topLeftCell="A2"/><selection pane="bottomLeft" activeCell="A2" sqref="A2"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="15"/><sheetData>')
            w('<row r="1">')
            for j, head in enumerate(headers, 1):
                w(f'<c r="{col(j)}1" s="1" t="inlineStr"><is><t>{xml(head)}</t></is></c>')
            w('</row>')
            kcol = headers.index('priority_key')
            scol = headers.index('input_file_type')
            for source_row, values in enumerate(reader):
                if source_row < START:
                    continue
                if source_row >= END:
                    break
                row_count += 1
                r = row_count + 1
                if len(values) != len(headers):
                    raise ValueError(f'row {r}: {len(values)} fields, expected {len(headers)}')
                key = values[kcol]
                if key in keys: dupes += 1
                keys.add(key)
                source_counts[values[scol]] += 1
                w(f'<row r="{r}">')
                for j, value in enumerate(values, 1):
                    if not value: continue
                    ref = f'{col(j)}{r}'
                    formula = fml(headers[j-1], r)
                    if formula is not None:
                        typ = ' t="b"' if value in ('True','False','TRUE','FALSE') else ''
                        cache = '1' if value.lower() == 'true' else '0' if value.lower() == 'false' else value
                        w(f'<c r="{ref}"{typ}><f>{xml(formula)}</f><v>{cache}</v></c>')
                        formula_count += 1
                    elif value in ('True','False','TRUE','FALSE'):
                        w(f'<c r="{ref}" t="b"><v>{1 if value.lower()=="true" else 0}</v></c>')
                    elif NUM.fullmatch(value) and headers[j-1] not in ('mun_geocodigo','mun_geocodigo_norm','property_code','property_code_norm','NUMEROESTA','PROTOCOLO'):
                        w(f'<c r="{ref}"><v>{value}</v></c>')
                    else:
                        w(f'<c r="{ref}" t="inlineStr"><is><t>{xml(value)}</t></is></c>')
                w('</row>')
                if row_count % 25000 == 0:
                    print('written', row_count, flush=True)
            w('</sheetData>')
            w(f'<autoFilter ref="A1:{col(len(headers))}{row_count+1}"/></worksheet>')
    print('rows', row_count, 'columns', len(headers), 'unique_keys', len(keys), 'duplicates', dupes, 'formulas', formula_count, 'sources', dict(source_counts), 'bytes', os.path.getsize(DEST), flush=True)
    if dupes or row_count != END-START:
        raise ValueError('count or uniqueness check failed')
