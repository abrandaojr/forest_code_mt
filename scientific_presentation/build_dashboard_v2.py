from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pptx import Presentation
from pptx.util import Inches

ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'out'/'fig'; HW=ROOT/'qa'/'presentation'/'scratch'/'assets'
PRE=ROOT/'qa'/'presentation'/'dashboard_v2'; PRE.mkdir(parents=True,exist_ok=True)
OUT=ROOT/'deliverables'/'04_presentation'/'forest_code_mt_paper_dashboard_final.pptx'
W,H=1600,900
BG='#F3F2F0'; INK='#35247B'; GREEN='#1F7F53'; ORANGE='#EC4F6D'; BLUE='#08AAA8'; GOLD='#F6D65B'; MUTED='#65716D'; LINE='#D8DED7'; WHITE='#FFFFFF'; DARK='#102F2B'
WEB=ROOT/'deliverables'/'04_presentation'/'assets'/'template_inspiration'
SERIF='C:/Windows/Fonts/arial.ttf'; SERIFB='C:/Windows/Fonts/arialbd.ttf'; SANS='C:/Windows/Fonts/arial.ttf'; SANSB='C:/Windows/Fonts/arialbd.ttf'
def font(path,size): return ImageFont.truetype(path,size)
def cover(im, path, box, contain=True, pad=0):
    x,y,w,h=box; src=Image.open(path).convert('RGBA')
    scale=min(w/src.width,h/src.height) if contain else max(w/src.width,h/src.height)
    src=src.resize((int(src.width*scale),int(src.height*scale)),Image.Resampling.LANCZOS)
    if not contain:
        l=max(0,(src.width-w)//2); t=max(0,(src.height-h)//2); src=src.crop((l,t,l+w,t+h))
    im.alpha_composite(src,(int(x+(w-src.width)/2),int(y+(h-src.height)/2)))
def txt(d,xy,text,size,color=INK,bold=False,serif=False,anchor='la',spacing=4):
    size=max(20,min(40,size))
    f=font(SERIFB if serif and bold else SERIF if serif else SANSB if bold else SANS,size)
    d.multiline_text(xy,text,font=f,fill=color,anchor=anchor,spacing=spacing)
def rounded(d,box,fill=WHITE,outline=LINE,r=18,width=2): d.rounded_rectangle(box,radius=r,fill=fill,outline=outline,width=width)
def fluid_bg(im, variant=0, strong=False):
    """Organic edge fields inspired by the supplied fluid-shapes template."""
    d=ImageDraw.Draw(im)
    if strong:
        d.ellipse((-170,-210,560,315),fill=ORANGE)
        d.ellipse((1320,-190,1770,260),fill=GOLD)
        d.ellipse((-190,690,330,1110),fill=BLUE)
    elif variant%3==0:
        d.ellipse((-145,730,240,1040),fill=ORANGE)
        d.ellipse((1450,-150,1730,150),fill=GOLD)
    elif variant%3==1:
        d.ellipse((-160,-160,190,175),fill=BLUE)
        d.ellipse((1450,740,1760,1050),fill=ORANGE)
    else:
        d.ellipse((-135,760,175,1030),fill=GOLD)
        d.ellipse((1470,-135,1760,160),fill=BLUE)
def silver_canvas():
    im=Image.new('RGBA',(W,H),BG)
    px=im.load()
    for y in range(H):
        for x in range(W):
            glow=int(10*(1-abs((x/W)-.42)))+int(5*(1-y/H))
            v=max(225,min(249,236+glow))
            px[x,y]=(v,v,v+1,255)
    return im
def base(section,page,title,subtitle):
    im=silver_canvas(); fluid_bg(im,page); d=ImageDraw.Draw(im)
    d.rectangle((0,0,16,H),fill=ORANGE)
    txt(d,(54,35),section.upper(),18,ORANGE,True)
    txt(d,(1545,35),f'{page:02d} / 14',17,MUTED,True,anchor='ra')
    txt(d,(54,72),title,38,INK,True,True)
    txt(d,(54,125),subtitle,18,MUTED)
    d.line((54,160,1546,160),fill=LINE,width=2)
    return im,d
def metric(d,x,y,value,label,color=GREEN,w=260):
    rounded(d,(x,y,x+w,y+112),WHITE,LINE,16,2); txt(d,(x+20,y+18),value,34,color,True,True); txt(d,(x+20,y+68),label,15,MUTED,True)
def panel(im,d,box,img,title=None):
    x,y,w,h=box; rounded(d,(x,y,x+w,y+h),WHITE,LINE,16,2)
    if title: txt(d,(x+18,y+15),title.upper(),14,MUTED,True); top=y+44
    else: top=y+10
    cover(im,img,(x+12,top,w-24,h-(top-y)-12),True)
def save(im,i):
    p=PRE/f'slide-{i:02d}.png'; im.convert('RGB').save(p,quality=95); return p

slides=[]
# 1 — cover
im=silver_canvas(); fluid_bg(im,1,True); d=ImageDraw.Draw(im)
cover(im,WEB/'nasa_cerrado_land_use_2000.jpg',(805,0,795,900),False)
d.rounded_rectangle((-80,-50,920,950),radius=150,fill=ORANGE)
d.ellipse((720,-120,1100,260),fill=ORANGE); d.ellipse((740,650,1080,1010),fill=BLUE)
txt(d,(70,70),'MATO GROSSO • PROPERTY-LEVEL EVIDENCE',18,'#9FD3B3',True)
txt(d,(70,145),'Forest Code\ncompliance,\nmade visible',64,WHITE,True,True,spacing=8)
txt(d,(74,430),'An auditable model of Legal Reserve, APP,\nregularization pathways and sensitivity.',25,'#D9E7DF')
d.line((74,550,620,550),fill=ORANGE,width=5)
txt(d,(74,590),'168,676',42,'#A9E0BE',True,True); txt(d,(270,603),'distinct rural-property records',18,WHITE)
txt(d,(74,660),'7.64 Mha',34,'#A9E0BE',True,True); txt(d,(245,672),'registered property area',18,WHITE)
txt(d,(74,805),'Scientific dashboard • methods, results, uncertainty and use',16,'#D3DCCE')
txt(d,(1515,865),'Satellite image: NASA Earth Observatory / Landsat',13,WHITE,True,anchor='ra')
slides.append(save(im,1))

# 2 — executive dashboard
im,d=base('Executive read',2,'The statewide result in one view','Four numbers summarize scale, exposure and the modeled response.')
metric(d,55,195,'168,676','distinct properties',GREEN,330); metric(d,405,195,'50.3%','active properties compliant',BLUE,330); metric(d,755,195,'4.36 Mha','total affected area',ORANGE,330); metric(d,1105,195,'3.35 Mha','assigned to compensation',INK,380)
panel(im,d,(55,335,720,490),FIG/'Figure_06_compliance_status.png','Property status')
panel(im,d,(805,335,680,490),FIG/'Figure_07_restoration_compensation.png','Regularization pathway')
slides.append(save(im,2))

# 3 — analytical architecture
im,d=base('Research design',3,'One property balance connects maps to legal obligations','The unit of analysis is the property record; the evidence chain stays visible.')
panel(im,d,(55,190,970,635),HW/'handwritten_data_pipeline.png','From records to a legal balance')
metric(d,1060,205,'3','CAR evidence tiers',GREEN,420); metric(d,1060,345,'11','input workbooks',BLUE,420); metric(d,1060,485,'0','formula mismatches',ORANGE,420)
rounded(d,(1060,635,1480,810),'#E9F2EC','#B8CEC0',16,2); txt(d,(1085,660),'WHY THIS MATTERS',15,GREEN,True); txt(d,(1085,700),'Every result can be traced\nback to a property input\nand a legal rule.',23,INK,True,True)
slides.append(save(im,3))

# 4 — evidence layers
im,d=base('Spatial evidence',4,'Compliance is reconstructed from multiple landscape layers','The model keeps legal, biophysical and tenure evidence separate before integration.')
imgs=['Figure_16A_APP_and_degraded_APP_spatial_inputs.png','Figure_16B_environmental_constraints_and_legal_reserve_inputs.png','Figure_16C_land_tenure_land_use_and_consolidated_area_inputs.png','Figure_16D_native_vegetation_RADAM_and_environmental_feature_inputs.png']
titles=['APP evidence','Legal Reserve constraints','Tenure and land use','Native vegetation']
for k,(nm,tt) in enumerate(zip(imgs,titles)):
    x=55+(k%2)*760; y=190+(k//2)*320; panel(im,d,(x,y,720,290),FIG/nm,tt)
slides.append(save(im,4))

# 5 — legal logic
im,d=base('Methods',5,'The calculation follows the law in a fixed sequence','Requirements, exemptions and available vegetation are resolved before pathways are assigned.')
panel(im,d,(55,190,970,635),HW/'handwritten_legal_logic.png','Legal logic, drawn as a decision system')
rounded(d,(1060,200,1485,375),'#123B35','#123B35',18,2); txt(d,(1085,225),'PROPERTY BALANCE',15,'#A9E0BE',True); txt(d,(1085,270),'Required area',25,WHITE,True,True); txt(d,(1085,310),'− eligible vegetation',25,WHITE,True,True); txt(d,(1085,350),'= deficit or surplus',25,'#F1A06E',True,True)
metric(d,1060,410,'APP','restoration obligation',ORANGE,425); metric(d,1060,550,'LR','restore or compensate',GREEN,425)
rounded(d,(1060,690,1485,810),'#FFF4EA','#F1C7A9',16,2); txt(d,(1085,715),'Interpretation',15,ORANGE,True); txt(d,(1085,750),'The model estimates legal exposure;\nit does not adjudicate a property.',19,INK,True)
slides.append(save(im,5))

# 6 — sample structure
im,d=base('Sample',6,'Small properties dominate the count; large properties dominate the land','The same statewide percentage can imply very different enforcement workloads.')
panel(im,d,(55,195,720,590),FIG/'chart_properties_by_input.png','Property records by evidence tier')
panel(im,d,(805,195,680,590),FIG/'Figure_08_mean_deficit_size.png','Average deficit by property size')
txt(d,(75,805),'51.9% of records are minifundia',20,GREEN,True); txt(d,(825,805),'Large properties contain 66.1% of registered area',20,ORANGE,True)
slides.append(save(im,6))

# 7 — vegetation basis
im,d=base('Biophysical basis',7,'Native vegetation accounting spans 65.89 million hectares','Forest and Cerrado formations create distinct Legal Reserve baselines.')
panel(im,d,(55,190,900,635),FIG/'Figure_10_vegetation_cover.png','Vegetation cover used by the model')
metric(d,995,205,'38.99 Mha','forest formation',GREEN,490); metric(d,995,350,'26.90 Mha','Cerrado formation',ORANGE,490)
rounded(d,(995,500,1485,805),'#EAF1EE','#BFD0C8',18,2); txt(d,(1020,528),'READ THE DENOMINATOR',15,GREEN,True); txt(d,(1020,570),'Legal Reserve percentages\ndiffer by vegetation formation.\nThe map comes before the rule.',27,INK,True,True,spacing=8)
slides.append(save(im,7))

# 8 — compliance and response
im,d=base('Main result',8,'Half of active properties are compliant; hectares tell a different story','Status measures breadth. Affected area measures the burden that must be resolved.')
panel(im,d,(55,195,690,590),FIG/'Figure_06_compliance_status.png','How many properties?')
panel(im,d,(775,195,710,590),FIG/'Figure_07_restoration_compensation.png','How many hectares?')
txt(d,(75,805),'75,554 affected properties',22,ORANGE,True); txt(d,(795,805),'0.48 Mha restoration  •  3.35 Mha compensation',22,GREEN,True)
slides.append(save(im,8))

# 9 — regularization flow
im,d=base('Pathways',9,'Compensation is the dominant Legal Reserve response','APP remains a restoration obligation; adjusted LR deficits can follow two paths.')
panel(im,d,(55,195,1430,590),ROOT/'scientific_presentation'/'assets'/'fig18_legal_reserve_deficit_pathways_sankey.png','From gross deficit to regularization pathway')
txt(d,(75,805),'The pathway mix is a modeled allocation under the baseline rules.',18,MUTED,True)
slides.append(save(im,9))

# 10 — scenarios
im,d=base('Sensitivity',10,'Legal history changes the estimate more than vegetation recovery','Two scenarios expose where the statewide result is most assumption-sensitive.')
panel(im,d,(55,195,690,470),FIG/'Figure_12_cons2000_total_scenario.png','Historical 2000 rule')
panel(im,d,(775,195,710,470),FIG/'Figure_11_secondary_vegetation_impact.png','Secondary vegetation')
metric(d,55,700,'−3.62 Mha','liability with the 2000 rule',GREEN,690); metric(d,775,700,'−0.85 Mha','liability when secondary vegetation counts',ORANGE,710)
slides.append(save(im,10))

# 11 — spatial dashboard
im,d=base('Spatial concentration',11,'Liability clusters in a limited set of municipalities','Three maps separate total exposure from its APP and Legal Reserve components.')
for k,(nm,tt) in enumerate([('map_total_deficit_ha.png','Total'),('map_rl_adjusted_deficit_ha.png','Legal Reserve'),('map_app_gross_deficit_ha.png','APP')]):
    panel(im,d,(55+k*510,195,470,600),FIG/nm,tt)
txt(d,(55,815),'Use totals to locate burden; use component maps to choose the response.',20,INK,True)
slides.append(save(im,11))

# 12 — municipal diagnostics
im,d=base('Municipal diagnostics',12,'Counts and hectares answer different policy questions','The paired panels keep prevalence separate from the average burden among affected properties.')
panel(im,d,(55,190,710,620),FIG/'Figure_09A_municipal_noncompliance_panel_1_of_2.png','APP and overall exposure')
panel(im,d,(795,190,690,620),FIG/'Figure_09B_municipal_noncompliance_panel_2_of_2.png','Legal Reserve and sensitivity')
slides.append(save(im,12))

# 13 — supply chains
im,d=base('Application',13,'45,637 supplier properties connect compliance to cattle flows','Direct suppliers carry the largest modeled exposure and the strongest scenario effect.')
panel(im,d,(55,195,700,585),FIG/'Figure_14_supplier_groups_subgroups.png','Supplier groups')
panel(im,d,(785,195,700,585),FIG/'Figure_15_supplier_cons2000_scenario.png','Effect of the 2000 rule')
txt(d,(75,805),'Direct suppliers: 20,316 properties',21,GREEN,True); txt(d,(805,805),'0.84 Mha with rule  •  1.73 Mha without',21,ORANGE,True)
slides.append(save(im,13))

# 14 — landing
im=Image.new('RGBA',(W,H),INK); d=ImageDraw.Draw(im)
cover(im,WEB/'un_page_mato_grosso_cattle.jpg',(870,0,730,900),False)
d.rectangle((0,0,1010,900),fill=INK)
d.ellipse((790,-150,1110,210),fill=GOLD); d.ellipse((790,690,1130,1030),fill=ORANGE)
txt(d,(65,55),'CONCLUSION',18,'#A9E0BE',True)
txt(d,(65,115),'Property-level transparency\nturns a statewide total\ninto an operating system.',48,WHITE,True,True,spacing=9)
for i,(n,l,c) in enumerate([('01','Screen every record','Breadth'),('02','Prioritize hectare burden','Scale'),('03','Test legal assumptions','Uncertainty'),('04','Connect properties to markets','Action')]):
    y=500+i*74; d.line((70,y+60,790,y+60),fill='#5E4DA0',width=2); txt(d,(75,y),n,25,ORANGE,True,True); txt(d,(145,y+2),l,23,WHITE,True); txt(d,(770,y+5),c.upper(),15,'#A9E0BE',True,anchor='ra')
txt(d,(75,840),'Mato Grosso Forest Code model • reproducible Python + property-level Excel formulas',15,'#8EA49D')
txt(d,(1510,865),'Photo: UN PAGE • Mato Grosso Goes Green',13,WHITE,True,anchor='ra')
slides.append(save(im,14))

# Build a PowerPoint with pixel-perfect full-slide compositions.
prs=Presentation(); prs.slide_width=Inches(13.333333); prs.slide_height=Inches(7.5)
blank=prs.slide_layouts[6]
for p in slides:
    s=prs.slides.add_slide(blank); s.shapes.add_picture(str(p),0,0,width=prs.slide_width,height=prs.slide_height)
prs.core_properties.title='Forest Code compliance at landscape scale — scientific dashboard'
prs.core_properties.author='Amintas'
prs.save(OUT)

# Contact sheet for visual QA.
thumbs=[]
for p in slides:
    x=Image.open(p).convert('RGB').resize((400,225),Image.Resampling.LANCZOS); thumbs.append(x)
sheet=Image.new('RGB',(1200,((len(thumbs)+2)//3)*250),'white')
sd=ImageDraw.Draw(sheet)
for i,t in enumerate(thumbs):
    x=(i%3)*400; y=(i//3)*250; sheet.paste(t,(x,y)); sd.text((x+8,y+228),f'{i+1:02d}',font=font(SANSB,13),fill=INK)
sheet.save(PRE/'contact_sheet.png')
print(OUT); print(PRE/'contact_sheet.png')
