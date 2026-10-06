import csv
P=r'outputs\codigo_florestal_mt_inputs_completos.csv'
names=['input_file_type','priority_key','area_ha_car','radam_forest_ha','radam_cerrado_ha','radam_total_ha','rl_exist_forest_ha','rl_exist_cerrado_ha','arl_declared_ha','simcar_validado__raw__arl_declared_ha','simcar_validado__raw__radam_forest_nveg24_ha','simcar_validado__raw__radam_cerrado_nveg24_ha','simcar_validado__raw__rl_exist_forest_ha','simcar_validado__raw__rl_exist_cerrado_ha']
with open(P,encoding='utf-8',newline='') as f:
 r=csv.DictReader(f)
 for i,row in enumerate(r):
  if i in (0,2,4,7):
   print(i,[(x,row.get(x,'')) for x in names])
  if i>7:break
