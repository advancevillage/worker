#!/usr/bin/env python3
"""Trace a reviewed x-monotone color boundary; emit an unconfirmed review proposal."""
import argparse
import math
from pathlib import Path
from PIL import Image,ImageDraw
from common import sha256,write_json
from readalong import read
from extract_content import polygon_points,polygon_string


def simplify(points,tolerance):
    if len(points)<=2:return points
    a,b=points[0],points[-1];dx=b[0]-a[0];dy=b[1]-a[1]
    length=math.hypot(dx,dy)
    distances=[abs(dy*(p[0]-a[0])-dx*(p[1]-a[1]))/length if length else math.dist(p,a) for p in points]
    i=max(range(len(points)),key=distances.__getitem__)
    if distances[i]<=tolerance:return [a,b]
    return simplify(points[:i+1],tolerance)[:-1]+simplify(points[i:],tolerance)


def trace(image,anchors,radius=90,tolerance=2.5):
    """Blue/light region below warm region; other boundaries need a different reviewed mask."""
    im=Image.open(image).convert('RGB');pixels=im.load();w,h=im.size
    if anchors[0][0]!=0 or anchors[-1][0]!=w-1 or any(a[0]>=b[0] for a,b in zip(anchors,anchors[1:])):
        raise ValueError('Anchors must cover image width with increasing x')
    traced=[];segment=0
    for x in range(w):
        while segment+1<len(anchors)-1 and x>anchors[segment+1][0]:segment+=1
        a,b=anchors[segment:segment+2];expected=a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0])
        candidates=[]
        for y in range(max(4,round(expected)-radius),min(h-4,round(expected)+radius+1)):
            above=pixels[x,y-3];below=pixels[x,y+3]
            if below[2]<170 or below[1]<175 or below[2]<below[0]-25:continue
            gain=below[2]-above[2]
            if gain<30:continue
            score=gain-.7*abs(y-expected)
            candidates.append((score,y))
        if not candidates:raise ValueError(f'tell-me: no reliable color boundary at x={x}')
        traced.append((x,max(candidates)[1]))
    from statistics import median
    smoothed=[(x,round(median(y for _,y in traced[max(0,x-3):min(w,x+4)]))) for x in range(w)]
    boundary=simplify(smoothed,tolerance)
    points=boundary+[(w-1,h-1),(0,h-1)]
    value=polygon_string(points);polygon_points(value,w,h)
    return value,traced


def main():
    p=argparse.ArgumentParser();p.add_argument('--image',type=Path,required=True);p.add_argument('--review',type=Path,required=True)
    p.add_argument('--region',required=True);p.add_argument('--anchors',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();review=read(a.review)
    if review['image_sha256']!=sha256(a.image):raise ValueError('Review hash mismatch')
    polygon,trace_points=trace(a.image,read(a.anchors))
    matches=[r for r in review['regions'] if r['id']==a.region]
    if len(matches)!=1:raise ValueError('Region not unique')
    matches[0].update(polygon=polygon,reviewed=False,provenance='color_boundary_trace_pending_visual_review')
    write_json(a.output,review)
    write_json(a.output.with_suffix('.trace.json'),trace_points)
    overlay=Image.open(a.image).convert('RGB');points=polygon_points(polygon,*overlay.size)
    ImageDraw.Draw(overlay).line(points+points[:1],fill=(20,70,230),width=2)
    overlay.save(a.output.with_suffix('.overlay.jpg'),quality=95)
    print(f'Proposal: {len(points)} vertices; requires visual confirmation')

if __name__=='__main__':main()
