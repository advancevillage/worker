#!/usr/bin/env python3
"""Create a reviewed-input proposal for a rerendered image; never approves scaled polygons."""
import argparse
import copy
from pathlib import Path
from common import sha256,write_json
from readalong import image_info,image_pid,media_type,read,validate_page,image_name
from extract_content import polygon_points,polygon_string


def migrate(old,image):
    validate_page(old)
    w,h=image_info(image);pid=image_pid(image)
    areas=copy.deepcopy(old['areas'])
    for area in areas:
        pts=polygon_points(area['polygon'],old['width'],old['height'])
        area['polygon']=polygon_string([(min(w-1,round(x*w/old['width'])),min(h-1,round(y*h/old['height']))) for x,y in pts])
        for asset in area['edurich']['assets'].values():
            if asset['uri']==f"asset:image/{image_name(old['pid'])}":
                asset.update(uri=f'asset:image/{pid}',mediaType=media_type(pid),width=w,height=h)
    page=dict(pid=pid,width=w,height=h,areas=areas)
    validate_page(page,image)
    return dict(image_sha256=sha256(image),reviewed=False,areas=areas)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--old',type=Path,required=True);p.add_argument('--image',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    write_json(a.output,migrate(read(a.old),a.image))
