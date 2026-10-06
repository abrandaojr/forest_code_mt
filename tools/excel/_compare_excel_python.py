import csv
import math
import os
from collections import Counter

src = r'outputs\codigo_florestal_mt_inputs_completos_recalculados.csv'
recalc = r'outputs\_formula_recalc_sample.tsv'
offset = int(os.environ.get('FC_OFFSET', '0'))
with open(src, encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    for _ in range(offset):
        next(reader)
    rows = [next(reader) for _ in range(100)]
counts = Counter()
examples = []
with open(recalc, encoding='utf-8') as f:
    for line in f:
        i, name, actual = line.rstrip('\n').split('\t', 2)
        expected = rows[int(i)][name]
        counts['checked'] += 1
        if expected.lower() in ('true','false'):
            ok = actual.lower() == expected.lower()
        elif expected.lower() == 'inf':
            ok = actual in ('1E+99','1e+99','1E99','1e99') or float(actual) >= 1e90
        else:
            try:
                a = float(actual)
                e = float(expected or 0)
                ok = math.isclose(a, e, rel_tol=1e-9, abs_tol=1e-7)
            except ValueError:
                ok = actual == expected
        if not ok:
            counts[name] += 1
            if len(examples) < 20:
                examples.append((i, name, expected, actual))
print('counts', dict(counts))
print('examples', examples)
