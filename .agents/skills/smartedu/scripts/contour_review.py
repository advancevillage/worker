"""Adaptive curve candidates, separate parts and hash-bound visual review evidence."""
import copy,hashlib,json,math
from pathlib import Path
from PIL import Image,ImageDraw
from common import sha256,write_json
from extract_content import polygon_points,intersects
from readalong import validate_page,document,add_module

def bezier(a,b,c,d,error=1.0,depth=0):
    if not 0<error<=10:raise ValueError('Invalid pixel error')
    def dist(p):
        dx=d[0]-a[0];dy=d[1]-a[1];den=dx*dx+dy*dy
        t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0
        return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
    if max(dist(b),dist(c))<=error:return [a,d]
    if depth>=20:raise ValueError('Curve subdivision limit')
    def mid(x,y):return ((x[0]+y[0])/2,(x[1]+y[1])/2)
    ab,bc,cd=mid(a,b),mid(b,c),mid(c,d);abc,bcd=mid(ab,bc),mid(bc,cd);m=mid(abc,bcd)
    return bezier(a,ab,abc,m,error,depth+1)[:-1]+bezier(m,bcd,cd,d,error,depth+1)

def checked_polygon(points,width,height):
    ps=[]
    for x,y in points:
        q=(round(x),round(y))
        if not ps or q!=ps[-1]:ps.append(q)
    if ps and ps[0]==ps[-1]:ps.pop()
    if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ps,ps[1:]+ps[:1]))<0:ps.reverse()
    value=':'.join(str(v) for p in ps for v in p)
    try:polygon_points(value,width,height)
    except ValueError as error:
        edges=list(zip(ps,ps[1:]+ps[:1]));bad=[]
        for i,(a,b) in enumerate(edges):
            for j,(c,d) in enumerate(edges):
                if j>i+1 and not(i==0 and j==len(edges)-1) and intersects(a,b,c,d):bad.append([i,j])
        raise ValueError(f'{error}; intersecting edge indices={bad[:12]}; inspect quantization/path, do not raise simplification tolerance') from error
    return value

def split_parts(image,page,index,polygons,labels):
    """Caller-confirmed separate components; never bridge gaps or duplicate text."""
    validate_page(page,image)
    if not 0<=index<len(page['areas']) or not polygons or len(polygons)!=len(labels):raise ValueError('Invalid parts')
    areas=copy.deepcopy(page['areas']);parts=[dict(polygon=polygons[0],edurich=areas[index]['edurich'])]
    for n,(poly,label) in enumerate(zip(polygons[1:],labels[1:]),1):
        d=document(f'part-{index}-{n}');add_module(d,'media')
        d['document']['body']=[dict(id=f'image-{n}',type='media:image',assetId='part',alt=label,decorative=False)]
        d['assets']['part']=dict(uri='asset:image/'+page['pid'],mediaType='image/png' if page['pid'].endswith('.png') else 'image/jpeg',width=page['width'],height=page['height'])
        parts.append(dict(polygon=poly,edurich=d))
    areas[index:index+1]=parts;candidate=dict(page,areas=areas);validate_page(candidate,image)
    return dict(image_sha256=sha256(image),reviewed=False,areas=areas)

def evidence(image,old,candidate,output,roi=None):
    """Source/outline comparisons plus independent pending acceptance results."""
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with Image.open(image) as im:source=im.convert('RGB')
    validate_page(old,image);validate_page(dict(old,areas=candidate['areas']),image)
    for name,areas in [('source',[]),('before',old['areas']),('after',candidate['areas'])]:
        im=source.copy();draw=ImageDraw.Draw(im)
        for a in areas:
            pts=polygon_points(a['polygon'],*im.size);draw.line(pts+pts[:1],fill=(0,70,220),width=2)
        if roi:im=im.crop(roi)
        im.save(output/(name+'.png'))
    write_json(output/'candidate.review.json',candidate)
    record=dict(image_sha256=sha256(image),candidate_sha256=sha256(output/'candidate.review.json'),
                checks=dict(geometry='passed',content='pending',visual='pending',interaction='pending'))
    write_json(output/'review-evidence.json',record)
    return record
