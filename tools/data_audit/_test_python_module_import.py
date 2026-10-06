import sys
print('start',flush=True)
import pandas as pd
print('pandas',pd.__version__,flush=True)
sys.path.insert(0,r'delivery_2026-09-03\07_code')
import _11_forest_code_compliance as compliance
print('compliance_loaded',compliance.DEFAULT_RULES,flush=True)
