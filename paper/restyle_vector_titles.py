"""Standardize existing vector titles without resampling or reconstructing curves."""
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import pymupdf as fitz
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'figures/redesigned'
BACKUP=ROOT/'tmp/figure_style_originals'
BACKUP.mkdir(parents=True,exist_ok=True)
NS='http://www.w3.org/2000/svg'
ET.register_namespace('',NS)
FONT='C:/Windows/Fonts/times.ttf'
# Existing plots retain every vector path; only text is replaced.
settings={
'fig01_mechanism': [('Task execution generates opportunities and evidence','Task execution generates opportunities and evidence',7.776,11.3)],
'fig02_cost_formation': [
('Strategy evolution','(a) Strategy evolution',7.776,25.5),
('Completion opportunities','(b) Completion opportunities',7.776,169.243049),
('Visible cost ranking','(c) Visible cost ranking',176.80,169.243049),
('Strategy transfer','(d) Strategy transfer',345.83,169.243049)],
'fig03_engineering_paths': [
('a  Communication 0 s','(a) Communication 0 s',7.776,61.16),
('b  Communication 900 s','(b) Communication 900 s',180.0,61.16),
('c  Communication 3600 s','(c) Communication 3600 s',353.0,61.16)]}
for name,changes in settings.items():
 for ext in ['pdf','svg']:
  source=OUT/f'{name}.{ext}';backup=BACKUP/source.name
  if not backup.exists():shutil.copy2(source,backup)
 doc=fitz.open(BACKUP/f'{name}.pdf');page=doc[0]
 lines=[l for b in page.get_text('dict')['blocks'] for l in b.get('lines',[])]
 wanted={old for old,_,_,_ in changes}
 if name=='fig02_cost_formation':wanted.update(['a','b','c','d'])
 found=set()
 for line in lines:
  text=''.join(s['text'] for s in line['spans'])
  if text in wanted:
   page.add_redact_annot(fitz.Rect(line['bbox']),fill=False);found.add(text)
 assert found==wanted,(name,wanted-found)
 page.apply_redactions(images=0,graphics=0)
 page.insert_font(fontname='TimesPanel',fontfile=FONT)
 for _,new,x,y in changes:page.insert_text((x,y),new,fontname='TimesPanel',fontsize=9,color=(.137,.208,.267))
 if name=='fig02_cost_formation':
  result=fitz.open();target=result.new_page(width=page.rect.width,height=page.rect.height)
  # Shift the top panel 10 pt down into its existing inter-row whitespace.
  for src,dst in [(fitz.Rect(0,0,518.4,19),fitz.Rect(0,0,518.4,19)),(fitz.Rect(0,19,518.4,144),fitz.Rect(0,29,518.4,154)),(fitz.Rect(0,154,518.4,291.6),fitz.Rect(0,154,518.4,291.6))]:
   target.show_pdf_page(dst,doc,0,clip=src)
 else:result=doc
 result.save(OUT/f'{name}.pdf',garbage=4,deflate=True)
 result[0].get_pixmap(matrix=fitz.Matrix(3,3),alpha=False).save(OUT/f'{name}.png')
 # Keep editable SVG export in sync with the PDF.
 tree=ET.parse(BACKUP/f'{name}.svg');root=tree.getroot()
 mappings={old:(new,x,y) for old,new,x,y in changes}
 for g in root.findall('.//{'+NS+'}g'):
  for text in list(g.findall('{'+NS+'}text')):
   if text.text in mappings:
    new,x,y=mappings[text.text];text.text=new;text.set('x',str(x));text.set('y',str(y));text.attrib.pop('transform',None)
    text.set('style',"font-size: 9px; font-family: 'Times New Roman'; text-anchor: start; fill: #233544")
   elif name=='fig02_cost_formation' and text.text in ['a','b','c','d']:g.remove(text)
  if name=='fig02_cost_formation' and g.get('id')=='axes_1':g.set('transform','translate(0 10)')
 tree.write(OUT/f'{name}.svg',encoding='utf-8',xml_declaration=True)
 print('Preserved vector content and updated titles:',name)

# Preserve the requested panel-c reference styling when titles are regenerated.
from soften_cost_zero import soften_cost_zero
soften_cost_zero()
