#!/usr/bin/env python3
"""Render reviewed Chinese replacements onto explicitly confirmed solid backgrounds."""
import argparse
import copy
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from common import sha256, write_json
from readalong import bilingual, image_name, document, paragraph, polygon_points, read, tell_me, text_blocks, validate_page


def render(root,page,review,font_path):
    root=Path(root);pid=page['pid'];source=root/'image'/image_name(pid)
    validate_page(page,source)
    if review.get('pid')!=pid or review.get('reviewed') is not True or review.get('page_sha256')!=sha256(root/'content'/'edurich'/f'{pid}.json'):
        raise ValueError('Render review must match current page JSON and be confirmed')
    replacements=review.get('replacements',[])
    english=[a for a in page['areas'] if bilingual(a['edurich'])]
    if len(replacements)!=len(english) or not english:raise ValueError('Review must cover every English area exactly once')
    im=Image.open(source).convert('RGB');draw=ImageDraw.Draw(im);trans=[]
    used=set()
    for replacement in replacements:
        candidates=[(i,a) for i,a in enumerate(page['areas']) if a['polygon']==replacement['source_polygon'] and bilingual(a['edurich'])]
        if len(candidates)!=1 or candidates[0][0] in used:raise ValueError('Ambiguous/duplicate translated area')
        i,area=candidates[0];used.add(i)
        if replacement.get('background_confirmed') is not True:raise ValueError('Complex or unconfirmed background: tell-me')
        # First implementation deliberately requires confirmed axis-aligned solid rectangles.
        points=polygon_points(replacement['polygon'],im.width,im.height)
        x0=min(x for x,y in points);x1=max(x for x,y in points);y0=min(y for x,y in points);y1=max(y for x,y in points)
        if points!=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]:raise ValueError('Translation compositor requires confirmed rectangular text mask')
        source_points=polygon_points(area['polygon'],im.width,im.height)
        if any(not(x0<=x<=x1 and y0<=y<=y1) for x,y in source_points):raise ValueError('Replacement does not cover original text')
        color=replacement['background']
        if not isinstance(color,list) or len(color)!=3 or any(type(c)is not int or not 0<=c<=255 for c in color):raise ValueError('Invalid confirmed background RGB')
        text=text_blocks(area['edurich'])[1]
        lines=None
        for size in range(replacement.get('max_font',36),replacement.get('min_font',18)-1,-1):
            font=ImageFont.truetype(str(font_path),size)
            candidate=[];line=''
            for c in text:
                if draw.textlength(line+c,font=font)>x1-x0-12:
                    if not line:raise ValueError('Translated character exceeds box width')
                    candidate.append(line);line=c
                else:line+=c
            if line:candidate.append(line)
            ascent,descent=font.getmetrics();line_height=ascent+descent+4
            if len(candidate)*line_height<=y1-y0-12:lines=candidate;break
        if lines is None:raise ValueError('Chinese translation overflows; tell-me')
        draw.rectangle((x0,y0,x1,y1),fill=tuple(color))
        for j,line in enumerate(lines):draw.text((x0+6,y0+6+j*line_height),line,font=font,fill=(0,0,0),anchor='lt')
        doc=document(f'{pid}-trans-{i}','zh');doc['document']['body']=[paragraph('text',text)]
        trans.append({'polygon':replacement['polygon'],'edurich':doc})
    # Preserve unchanged Chinese/illustration areas in translated-image reading order.
    by_source={r['source_polygon']:a for r,a in zip(replacements,trans)}
    result=copy.deepcopy(page)
    result['trans']=[by_source[a['polygon']] if bilingual(a['edurich']) else copy.deepcopy(a) for a in page['areas']]
    validate_page(result)
    target=root/'trans'/image_name(pid);target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix('.part');im.save(temp,format='PNG' if image_name(pid).endswith('.png') else 'JPEG',**({} if image_name(pid).endswith('.png') else {'quality':95}));os.replace(temp,target)
    write_json(root/'content'/'edurich'/f'{pid}.json',result)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--pid',required=True)
    p.add_argument('--review',type=Path,required=True);p.add_argument('--font',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True)
    a=p.parse_args()
    try:render(a.root,read(a.root/'content'/'edurich'/f'{a.pid}.json'),read(a.review),a.font);return 0
    except (ValueError,OSError) as e:tell_me(a.work_dir,a.pid,e);return 2

if __name__=='__main__':raise SystemExit(main())
