import zipfile
import xml.etree.ElementTree as ET

p = r'outputs\codigo_florestal_mt_todas_propriedades_168676.xlsx'
with zipfile.ZipFile(p) as z:
    print('bad_zip_entry', z.testzip(), flush=True)
    with z.open('xl/worksheets/sheet1.xml') as f:
        rows = formulas = 0
        last = None
        for event, e in ET.iterparse(f, events=('end',)):
            if e.tag.endswith('}f'):
                formulas += 1
            if e.tag.endswith('}row'):
                rows += 1
                last = e.attrib.get('r')
                e.clear()
        print('xml_rows', rows, 'last_row', last, 'formulas', formulas, flush=True)
