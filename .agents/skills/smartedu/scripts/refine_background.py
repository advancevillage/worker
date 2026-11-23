#!/usr/bin/env python3
"""Propose a local background/border polygon for a flat area; requires visual review."""
import argparse
import copy
from collections import deque, defaultdict
from pathlib import Path
from PIL import Image, ImageDraw
from common import sha256, write_json
from extract_content import polygon_points, polygon_string
from readalong import read, validate_page
from refine_regions import simplify


def contour(image, roi, seed, color=None, tolerance=28, error=1.5):
    with Image.open(image) as source:
        im=source.convert('RGB')
    w,h=im.size
    x0,y0,x1,y1=roi;sx,sy=seed
    if not (0<=x0<sx<x1<w and 0<=y0<sy<y1<h):
        raise ValueError('tell-me: seed/ROI must be inside image')
    if not 0<=tolerance<=100 or not 0<error<=10:
        raise ValueError('Invalid tolerance/error')
    if (x1-x0)*(y1-y0)>4_000_000:raise ValueError('Local ROI exceeds 4MP')
    pix=im.load();color=tuple(color or pix[sx,sy])
    def matches(x,y):return max(abs(a-b) for a,b in zip(pix[x,y],color))<=tolerance
    if not matches(sx,sy):raise ValueError('tell-me: seed differs from selected color')
    component=set();seen={(sx,sy)};queue=deque([(sx,sy)])
    while queue:
        x,y=queue.popleft();component.add((x,y))
        if x in (x0,x1) or y in (y0,y1):
            raise ValueError('tell-me: background reaches ROI edge; expand ROI or confirm separation')
        for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if p not in seen:
                seen.add(p)
                if matches(*p):queue.append(p)
    if len(component)<20:raise ValueError('tell-me: insufficient connected background')
    edges=defaultdict(set)
    for x,y in component:
        if (x,y-1) not in component:edges[(x,y)].add((x+1,y))
        if (x+1,y) not in component:edges[(x+1,y)].add((x+1,y+1))
        if (x,y+1) not in component:edges[(x+1,y+1)].add((x,y+1))
        if (x-1,y) not in component:edges[(x,y+1)].add((x,y))
    directions={(1,0):0,(0,1):1,(-1,0):2,(0,-1):3}
    loops=[]
    while edges:
        start=next(iter(edges));cur=start;loop=[start];direction=None
        while True:
            options=edges[cur]
            if direction is None:nxt=next(iter(options))
            else:
                def rank(p):
                    turn=(directions[(p[0]-cur[0],p[1]-cur[1])]-direction)%4
                    return {1:0,0:1,3:2,2:3}[turn]
                nxt=min(options,key=rank)
            direction=directions[(nxt[0]-cur[0],nxt[1]-cur[1])]
            options.remove(nxt)
            if not options:del edges[cur]
            cur=nxt
            if cur==start:break
            loop.append(cur)
        loops.append(loop)
    def signed_area(ps):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ps,ps[1:]+ps[:1]))/2
    outer=max(loops,key=signed_area)
    # Two open halves preserve a closed contour while simplifying raster noise.
    split=max(range(len(outer)),key=lambda i:(outer[i][0]-outer[0][0])**2+(outer[i][1]-outer[0][1])**2)
    points=simplify(outer[:split+1],error)[:-1]+simplify(outer[split:]+outer[:1],error)[:-1]
    value=polygon_string(points);polygon_points(value,w,h)
    return value


def propose(image,page,area_index,roi,seed,color=None,tolerance=28,error=1.5,mode="enclose",required=None):
    validate_page(page,image)
    if not 0<=area_index<len(page['areas']):raise ValueError('Invalid area index')
    value=contour(image,roi,seed,color,tolerance,error)
    points=polygon_points(value,page['width'],page['height'])
    # The selected boundary must enclose the entire existing target region.
    mask=Image.new('1',(page['width'],page['height']));ImageDraw.Draw(mask).polygon(points,fill=1)
    if mode not in ('enclose','replace'):raise ValueError('Unknown proposal mode')
    if mode=='replace' and not required:raise ValueError('replace requires confirmed protected polygons')
    protected=[page['areas'][area_index]['polygon']] if mode=='enclose' else required
    oldmask=Image.new('1',mask.size)
    for value in protected:
        old=polygon_points(value,page['width'],page['height'])
        ImageDraw.Draw(oldmask).polygon(old,fill=1)
    from PIL import ImageChops
    if ImageChops.subtract(oldmask.convert('L'),mask.convert('L')).getbbox():
        raise ValueError('tell-me: selected boundary does not enclose target area')
    areas=copy.deepcopy(page['areas']);areas[area_index]['polygon']=value
    candidate=dict(page,areas=areas);validate_page(candidate,image)
    return dict(image_sha256=sha256(image),reviewed=False,areas=areas)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',type=Path,required=True);p.add_argument('--page',type=Path,required=True)
    p.add_argument('--area',type=int,required=True,help='Zero-based flat area index')
    p.add_argument('--roi',type=int,nargs=4,required=True);p.add_argument('--seed',type=int,nargs=2,required=True)
    p.add_argument('--color',type=int,nargs=3);p.add_argument('--tolerance',type=int,default=28)
    p.add_argument('--error',type=float,default=1.5);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=['enclose','replace'],default='enclose')
    p.add_argument('--protected',type=Path,help='Hash-bound JSON with confirmed:true and polygons preserving required content')
    a=p.parse_args()
    required=None
    if a.protected:
        proof=read(a.protected)
        if proof.get('image_sha256')!=sha256(a.image) or proof.get('confirmed') is not True:
            raise ValueError('Protected content must be confirmed and bound to the final image')
        required=proof['polygons']
    review=propose(a.image,read(a.page),a.area,a.roi,a.seed,a.color,a.tolerance,a.error,a.mode,required)
    write_json(a.output,review)
    with Image.open(a.image) as source:im=source.convert('RGB')
    points=polygon_points(review['areas'][a.area]['polygon'],*im.size)
    ImageDraw.Draw(im).line(points+points[:1],fill=(20,70,230),width=3)
    im.save(a.output.with_suffix('.overlay.png'))
    print(f'Proposal: {len(points)} vertices; requires visual review')

if __name__=='__main__':main()
