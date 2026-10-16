"""Apply the requested light zero reference to panel (c), preserving vectors."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import pymupdf as fitz
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'figures/redesigned'
def soften_cost_zero():
    pdf=OUT/'fig02_cost_formation.pdf'
    doc=fitz.open(pdf)
    # Match the original panel-c zero-line drawing, not any data path.
    pattern=rb'\.4509804 \.5058823 \.54509809 RG 2 J \.8 w (218\.27368 101\.42696 m 339\.00633 101\.42696 l S)'
    count=0
    for xref in range(1,doc.xref_length()):
        if not doc.xref_is_stream(xref): continue
        stream=doc.xref_stream(xref)
        updated,n=re.subn(pattern,rb'.78 .78 .78 RG 0 J .4 w [2 2] 0 d \1',stream)
        if n: doc.update_stream(xref,updated);count+=n
    assert count==1 or any(g.get('width') and abs(g['width']-.4)<1e-5 and g.get('color') and abs(g['color'][0]-.78)<1e-5 for g in doc[0].get_drawings()), 'Expected panel-c reference line missing'
    if count:
        temp=pdf.with_name(pdf.stem+'.updated.pdf')
        doc.save(temp,garbage=4,deflate=True);doc.close();temp.replace(pdf)
    else:doc.close()
    doc=fitz.open(pdf)
    doc[0].get_pixmap(matrix=fitz.Matrix(3,3),alpha=False).save(OUT/'fig02_cost_formation.png')
    doc.close()
    ns='http://www.w3.org/2000/svg';ET.register_namespace('',ns)
    svg=OUT/'fig02_cost_formation.svg';tree=ET.parse(svg)
    g=tree.find(".//{%s}g[@id='axes_3']/{%s}g[@id='line2d_31']"%(ns,ns))
    assert g is not None
    line=g.find('{%s}path'%ns);assert line is not None
    line.set('style','fill: none; stroke: #c7c7c7; stroke-width: 0.4; stroke-dasharray: 2,2; stroke-linecap: butt')
    tree.write(svg,encoding='utf-8',xml_declaration=True)
    print('Saved panel (c): light gray, dashed, 0.4 pt; original vector paths retained.')
if __name__=='__main__':soften_cost_zero()
