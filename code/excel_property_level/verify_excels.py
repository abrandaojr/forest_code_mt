import glob
import os
import zipfile

paths = [rf'outputs\codigo_florestal_mt_completo_formulas_parte_{i:02d}.xlsx' for i in range(1,12)]
assert len(paths) == 11, len(paths)
total_rows = total_formulas = 0
for i,path in enumerate(paths,1):
    with zipfile.ZipFile(path) as z:
        assert 'xl/worksheets/sheet2.xml' in z.namelist()
        with z.open('xl/worksheets/sheet1.xml') as f:
            head = f.read(100000)
            assert b'</row>' in head
            assert head.split(b'</row>', 1)[0].count(b'<c ') == 638
            carry = b''
            rows = formulas = 0
            f.seek(0)
            while chunk := f.read(1024*1024):
                block = carry + chunk
                rows += block.count(b'<row r="') - carry.count(b'<row r="')
                formulas += block.count(b'<f>') - carry.count(b'<f>')
                carry = block[-16:]
            assert carry.endswith(b'</worksheet>')
        expect = 16000 if i < 11 else 9533
        assert rows == expect + 1, (path, rows, expect)
        assert formulas == expect * 77, (path, formulas, expect*77)
        assert os.path.getsize(path) < 104857600
        print(i, 'rows', rows-1, 'formulas', formulas, 'bytes', os.path.getsize(path), flush=True)
        total_rows += rows-1
        total_formulas += formulas
print('total_rows',total_rows,'total_formulas',total_formulas)
assert total_rows == 169533
