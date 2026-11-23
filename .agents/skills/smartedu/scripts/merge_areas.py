#!/usr/bin/env python3
"""Merge confirmed container contents into one flat area; emit review=false proposal."""
import argparse
import copy
from pathlib import Path
from PIL import Image,ImageDraw,ImageChops
from common import sha256,write_json
from readalong import read,validate_page,document,image_pid,image_name,asset_name,media_type
from extract_content import polygon_points
from refine_background import contour


def merge(image,page,indices,polygon,review_dir,*,connected_confirmed=False):
    if connected_confirmed is not True:
        raise ValueError("tell-me: confirm a single connected container; separate thought dots must remain separate areas")
    image=Path(image);review_dir=Path(review_dir);validate_page(page,image)
    if len(indices)<2 or indices!=sorted(set(indices)) or indices[0]<0 or indices[-1]>=len(page['areas']):
        raise ValueError('Select distinct area indices in reading order')
    if indices!=list(range(indices[0],indices[-1]+1)):
        raise ValueError('tell-me: nonconsecutive areas require explicit reading-order review')
    points=polygon_points(polygon,page['width'],page['height'])
    mask=Image.new('1',(page['width'],page['height']));ImageDraw.Draw(mask).polygon(points,fill=1)
    langs={page['areas'][i]['edurich']['document']['metadata'].get('language') for i in indices}-{None}
    if langs-{'zh'}:raise ValueError('tell-me: bilingual merge requires translation review')
    merged=document('merged-'+str(indices[0]),'zh' if langs else None)
    with Image.open(image) as original:source=original.convert('RGB')
    for i in indices:
        area=page['areas'][i];oldpts=polygon_points(area['polygon'],*source.size)
        childmask=Image.new('1',source.size);ImageDraw.Draw(childmask).polygon(oldpts,fill=1)
        if ImageChops.subtract(childmask.convert('L'),mask.convert('L')).getbbox():
            raise ValueError('tell-me: container does not enclose selected contents')
        doc=copy.deepcopy(area['edurich']);merged['modules'].update(doc['modules'])
        for key,asset in doc['assets'].items():
            newkey=f'a{i}-{key}'
            if asset_name(asset)==image_name(page['pid']):
                x0=min(x for x,y in oldpts);x1=max(x for x,y in oldpts)+1
                y0=min(y for x,y in oldpts);y1=max(y for x,y in oldpts)+1
                crop=source.crop((x0,y0,x1,y1));cropmask=childmask.crop((x0,y0,x1,y1))
                crop=Image.composite(crop,Image.new('RGB',crop.size,'white'),cropmask)
                directory=review_dir/'image';directory.mkdir(parents=True,exist_ok=True)
                import io,hashlib
                buffer=io.BytesIO();crop.save(buffer,format='PNG');data=buffer.getvalue()
                name=hashlib.md5(data,usedforsecurity=False).hexdigest()+'.png';target=directory/name
                if target.exists() and target.read_bytes()!=data:raise ValueError('Image hash collision')
                target.write_bytes(data)
                asset=dict(uri=f'asset:image/{name}',mediaType='image/png',width=crop.width,height=crop.height)
            else:
                import shutil
                name=asset_name(asset);src=image.parent/name
                if image_pid(src)!=name:raise ValueError('Auxiliary image hash mismatch')
                directory=review_dir/'image';directory.mkdir(parents=True,exist_ok=True)
                dest=directory/name
                if dest.exists() and dest.read_bytes()!=src.read_bytes():raise ValueError('Asset collision')
                if src.resolve()!=dest.resolve():shutil.copyfile(src,dest)
            merged['assets'][newkey]=asset
        def rename(node):
            node['id']=f'a{i}-'+node['id']
            if 'assetId' in node:node['assetId']=f'a{i}-'+node['assetId']
            for child in node.get('children',[]):rename(child)
        for node in doc['document']['body']:
            rename(node);merged['document']['body'].append(node)
    areas=copy.deepcopy(page['areas']);areas[indices[0]:indices[-1]+1]=[dict(polygon=polygon,edurich=merged)]
    candidate=dict(page,areas=areas);validate_page(candidate,image)
    return dict(image_sha256=sha256(image),reviewed=False,areas=areas)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',type=Path,required=True);p.add_argument('--page',type=Path,required=True)
    p.add_argument('--areas',type=int,nargs='+',required=True);p.add_argument('--roi',type=int,nargs=4,required=True)
    p.add_argument('--seed',type=int,nargs=2,required=True);p.add_argument('--tolerance',type=int,default=10)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--connected-container-confirmed',action='store_true',help='Confirm selected contents share one physically connected container')
    a=p.parse_args();poly=contour(a.image,a.roi,a.seed,tolerance=a.tolerance)
    result=merge(a.image,read(a.page),a.areas,poly,a.output.parent,connected_confirmed=a.connected_container_confirmed);write_json(a.output,result)
    print('Merged proposal requires visual review:',a.output)

if __name__=='__main__':main()
