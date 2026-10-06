import csv
from collections import Counter
with open(r'out\table\forest_code_mt_priority_consolidated_with_secondary_20260818.csv', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    c = Counter(row['app_cap_ha'] for row in reader)
print(c.most_common(8))
