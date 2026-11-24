#!/usr/bin/env python3
"""Local OCR + reviewed layout → pixel polygons, EduRich draft, and inspection preview."""
import argparse
import base64
import html
import json
import math
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from common import read_json, sha256, write_json
from identify_pages import compile_ocr

VERSION = '0.1.0-draft'
MAX_PIXELS = 40_000_000


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def intersects(a, b, c, d):
    def on(p, q, r):
        return cross(p, q, r) == 0 and min(p[0], q[0]) <= r[0] <= max(p[0], q[0]) and min(p[1], q[1]) <= r[1] <= max(p[1], q[1])
    return (cross(a,b,c)*cross(a,b,d) < 0 and cross(c,d,a)*cross(c,d,b) < 0
            or on(a,b,c) or on(a,b,d) or on(c,d,a) or on(c,d,b))


def polygon_points(value, width, height):
    fields = value.split(':')
    if len(fields) < 6 or len(fields) % 2 or len(fields) > 1024 or any(not re.fullmatch(r'\d+', v) for v in fields):
        raise ValueError('Polygon needs 3–512 integer coordinate pairs')
    points = list(zip(map(int, fields[::2]), map(int, fields[1::2])))
    if len(set(points)) != len(points):
        raise ValueError('Polygon repeats a vertex')
    if any(not (0 <= x < width and 0 <= y < height) for x,y in points):
        raise ValueError('Polygon is outside image bounds')
    area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points, points[1:]+points[:1]))
    if area <= 0:
        raise ValueError('Polygon must have positive area and clockwise screen-coordinate order')
    edges = list(zip(points, points[1:]+points[:1]))
    for i,(a,b) in enumerate(edges):
        for j,(c,d) in enumerate(edges):
            if j <= i or j == i+1 or (i == 0 and j == len(edges)-1):
                continue
            if intersects(a,b,c,d):
                raise ValueError('Polygon self-intersects')
    return points


def polygon_string(points):
    return ':'.join(str(n) for point in points for n in point)


def rect_polygon(word, width, height):
    x0=max(0, math.floor(word['x0']*width)); y0=max(0, math.floor(word['y0']*height))
    x1=min(width-1, math.ceil(word['x1']*width)); y1=min(height-1, math.ceil(word['y1']*height))
    return polygon_string([(x0,y0),(x1,y0),(x1,y1),(x0,y1)])


def exclusion(word, printed_page):
    text = re.sub(r'\s+', '', word['text'])
    if '仅供个人学习使用' in text or '未经授权不得另做他用' in text:
        return 'source_watermark'
    if (printed_page is not None and text == str(printed_page) and word['y0'] > .86
            and (word['x1'] < .35 or word['x0'] > .65)):
        return 'printed_page_number'
    return None


def validate_edurich(doc):
    """Strict validation of the core/media subset emitted here, not a general renderer."""
    if len(json.dumps(doc,ensure_ascii=False,allow_nan=False).encode('utf-8'))>5_000_000:
        raise ValueError('EduRich subset document exceeds 5MB')
    if set(doc) != {'protocol','version','modules','document','assets','styles'}:
        raise ValueError('Unexpected EduRich root fields')
    if doc['protocol'] != 'edurich' or doc['version'] != VERSION:
        raise ValueError('Incorrect EduRich protocol/version')
    if doc['document']['profile'] != 'reflow' or not doc['document']['id']:
        raise ValueError('Invalid document profile/id')
    if doc['modules'].get('core') != {'version':VERSION,'required':True}:
        raise ValueError('core module must be required')
    if set(doc['document']) != {'id','metadata','profile','body'}:
        raise ValueError('Unexpected document fields')
    for module, value in doc['modules'].items():
        if module not in ('core','media') or value != {'version':VERSION,'required':True}:
            raise ValueError('Unsupported module')
    ids = set()
    if len(doc['document']['body'])>1000:
        raise ValueError('EduRich subset exceeds 1000 blocks')
    for block in doc['document']['body']:
        if not block.get('id') or block['id'] in ids:
            raise ValueError('Missing/duplicate node ID')
        ids.add(block['id'])
        if block['type'] in ('core:paragraph','core:heading'):
            fields = {'id','type','children'} | ({'level'} if block['type']=='core:heading' else set())
            if set(block) != fields:
                raise ValueError('Unexpected block fields')
            if block['type']=='core:heading' and (type(block['level']) is not int or not 1<=block['level']<=6 or not block['children']):
                raise ValueError('Invalid heading')
            for child in block['children']:
                if set(child) != {'id','type','value'} or child['type']!='core:text' or not isinstance(child['value'], str):
                    raise ValueError('Invalid inline text')
                if not child['id'] or child['id'] in ids:
                    raise ValueError('Missing/duplicate inline ID')
                ids.add(child['id'])
                if len(ids)>2000:
                    raise ValueError('EduRich subset exceeds 2000 nodes')
        elif block['type']=='media:image':
            if set(block) != {'id','type','assetId','alt','decorative'} or not block['alt'] or block['decorative']:
                raise ValueError('Invalid nondecorative image')
            if 'media' not in doc['modules'] or block['assetId'] not in doc['assets']:
                raise ValueError('Missing media module/asset')
        else:
            raise ValueError('Unsupported block type')
    for asset in doc['assets'].values():
        if set(asset) != {'uri','mediaType','width','height'} or not asset['uri'].startswith('asset:'):
            raise ValueError('Invalid asset fields/URI')
        if asset['mediaType']!='image/png' or any(type(asset[k]) is not int or asset[k]<=0 for k in ('width','height')):
            raise ValueError('Invalid asset dimensions/type')
    return ids


def build_content(image_path, words, review, output, printed_page=None):
    image_path, output = Path(image_path), Path(output)
    if image_path.stat().st_size > 30_000_000:
        raise ValueError('Input image exceeds 30MB')
    image = Image.open(image_path)
    width,height=image.size
    if width*height > MAX_PIXELS:
        raise ValueError('Decoded image exceeds 40MP')
    if image.getexif().get(274,1)!=1:
        raise ValueError('Normalize EXIF orientation before OCR')
    image.load(); digest=sha256(image_path)
    if review and review.get('image_sha256')!=digest:
        raise ValueError('Review belongs to another image revision')
    excluded = {}
    auto = []
    for i, word in enumerate(words):
        why=exclusion(word,printed_page)
        if why:
            excluded[why]=excluded.get(why,0)+1
            continue
        text=word['text']
        lang='zh-CN' if re.search(r'[\u4e00-\u9fff]',text) else 'und'
        auto.append(dict(id=f'ocr-{i+1}',kind='text',polygon=rect_polygon(word,width,height),
                         text=text,language=lang,role='paragraph',provenance='vision_ocr',
                         confidence=word.get('confidence',0),reviewed=False))
    regions = review['regions'] if review else auto
    if len(regions)>500:
        raise ValueError('More than 500 regions')
    document = dict(protocol='edurich',version=VERSION,
                    modules={'core':dict(version=VERSION,required=True)}, assets={},styles={},
                    document=dict(id='page-'+image_path.stem,metadata=dict(title=image_path.stem,language='zh-CN',subject='语文'),profile='reflow',body=[]))
    out_regions=[]; diagnostics=[]; seen=set(); asset_manifest={}
    def text_node(node_id,value,heading=False,level=1):
        node=dict(id=node_id,type='core:heading' if heading else 'core:paragraph',
                  children=[dict(id=node_id+'-text',type='core:text',value=value)])
        if heading:node['level']=level
        document['document']['body'].append(node)
        return node_id
    for index, region in enumerate(regions):
        rid=region['id']
        if not re.fullmatch('[a-zA-Z0-9_-]+',rid) or rid in seen:
            raise ValueError('Unsafe/duplicate region ID')
        seen.add(rid);points=polygon_points(region['polygon'],width,height)
        if region['kind'] not in ('text','illustration'):
            raise ValueError('Unsupported region kind')
        item={k:region[k] for k in ('id','kind','polygon')}
        item.update(reading_order=index+1,provenance=region.get('provenance','visual_review'),
                    reviewed=bool(region.get('reviewed',False)),node_ids=[])
        if region.get('parent_region_id'):item['parent_region_id']=region['parent_region_id']
        if region['kind']=='illustration':
            if not region.get('alt'):raise ValueError('Image region requires reviewed alt text')
            x0=min(x for x,y in points);x1=max(x for x,y in points)
            y0=min(y for x,y in points);y1=max(y for x,y in points)
            crop=image.crop((x0,y0,x1+1,y1+1)).convert('RGBA')
            mask=Image.new('L',crop.size,0)
            ImageDraw.Draw(mask).polygon([(x-x0,y-y0) for x,y in points],fill=255)
            crop.putalpha(mask)
            asset_path=Path('assets')/image_path.stem/(rid+'.png')
            (output/asset_path).parent.mkdir(parents=True,exist_ok=True);crop.save(output/asset_path)
            aid=rid+'-asset';nodeid=rid+'-image'
            document['modules']['media']=dict(version=VERSION,required=True)
            document['assets'][aid]=dict(uri='asset:'+image_path.stem+'/'+rid+'.png',mediaType='image/png',width=crop.width,height=crop.height)
            document['document']['body'].append(dict(id=nodeid,type='media:image',assetId=aid,alt=region['alt'],decorative=False))
            item['node_ids'].append(nodeid);asset_manifest[aid]=str(asset_path)
        if region['kind']=='text':
            text=region['text'];language=region.get('language','und')
            if not text or not isinstance(text,str):raise ValueError('Text region is empty')
            # Recheck reviewed text: manual region files cannot reintroduce a page number.
            normalized=dict(text=text,y0=min(y for x,y in points)/height,
                            x0=min(x for x,y in points)/width,x1=max(x for x,y in points)/width)
            if exclusion(normalized,printed_page):raise ValueError('Excluded page/watermark reintroduced by review')
            item['language']=language
            item['node_ids'].append(text_node(rid+'-source',text,region.get('role')=='heading',region.get('level',1)))
            if language=='en':
                translation=region.get('translation')
                if not translation or not re.search(r'[\u4e00-\u9fff]',translation):
                    raise ValueError('English requires a corresponding Chinese translation')
                item['translation']=dict(language='zh-CN',source='reviewed_translation',
                                         node_ids=[text_node(rid+'-translation',translation)])
            elif re.search('[A-Za-z]',text) and language not in ('zh-Latn','zh-Latn-pinyin'):
                diagnostics.append(dict(code='W_LANGUAGE_REVIEW',severity='warning',path=f'/regions/{index}',message='Latin text must be reviewed as English, pinyin, or other language'))
        if not item['reviewed']:
            diagnostics.append(dict(code='W_VISUAL_REVIEW',severity='warning',path=f'/regions/{index}',message='Unreviewed recognition/layout'))
        out_regions.append(item)
    ids=validate_edurich(document)
    for r in out_regions:
        if any(n not in ids for n in r['node_ids']+r.get('translation',{}).get('node_ids',[])):
            raise ValueError('Unresolved region node reference')
        if r.get('parent_region_id') and r['parent_region_id'] not in seen:
            raise ValueError('Unresolved parent region')
    result=dict(format='smartedu.content/0.1',image=dict(file=image_path.name,width=width,height=height,sha256=digest),
                coordinates=dict(origin='top-left',unit='pixel',x_direction='right',y_direction='down',polygon_format='x1:y1:x2:y2:...',vertex_order='clockwise'),
                status='reviewed_sample' if review and not diagnostics else 'needs_review',
                extraction=dict(method='local_vision_plus_manual_layout_review' if review else 'local_vision_text_only',
                                non_text_regions_automatic=False,excluded_counts=excluded),
                regions=out_regions,edurich=document,asset_manifest=asset_manifest,diagnostics=diagnostics)
    output.mkdir(parents=True,exist_ok=True)
    write_json(output/(image_path.stem+'.json'),result)
    write_json(output/(image_path.stem+'.edurich.json'),document)
    preview(image_path,result,output/(image_path.stem+'.preview.html'))
    return result


def preview(image_path, result, target):
    encoded=base64.b64encode(Path(image_path).read_bytes()).decode()
    with Image.open(image_path) as source: mime=Image.MIME[source.format]
    width,height=result['image']['width'],result['image']['height']
    polygons=[];rows=[]
    body={n['id']:n for n in result['edurich']['document']['body']}
    for region in result['regions']:
        points=polygon_points(region['polygon'],width,height)
        color='#dc2626' if region['kind']=='text' else '#2563eb'
        title=html.escape(region['id'])
        label=region['reading_order']
        polygons.append(f'<g><polygon points="{" ".join(f"{x},{y}" for x,y in points)}" stroke="{color}" fill="{color}" fill-opacity=".10" stroke-width="3"><title>{title}</title></polygon><text x="{points[0][0]}" y="{max(20,points[0][1]-5)}" fill="{color}" font-size="24">{label}</text></g>')
        text=' / '.join(''.join(c['value'] for c in body[n].get('children',[])) or body[n].get('alt','') for n in region['node_ids'])
        rows.append(f'<tr><td>{label}</td><td>{title}</td><td>{html.escape(region["kind"])}</td><td>{html.escape(text)}</td><td><code>{region["polygon"]}</code></td></tr>')
    page=f'''<!doctype html><meta charset="utf-8"><title>{html.escape(Path(image_path).stem)} 内容核对</title>
<style>body{{font:15px sans-serif;margin:24px}}main{{display:grid;grid-template-columns:minmax(400px,55%) 1fr;gap:24px}}svg{{width:100%;height:auto}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:8px;vertical-align:top}}code{{word-break:break-all}}button{{padding:8px;margin:8px}}g:hover polygon{{fill-opacity:.3}}@media(max-width:900px){{main{{display:block}}}}</style>
<h1>{html.escape(Path(image_path).name)} · {width} × {height}</h1><p>红色：文字；蓝色：插图。像素坐标原点在左上角。此页仅为区域叠加核对，非 EduRich 渲染。</p>
<button onclick="document.getElementById('regions').style.display=document.getElementById('regions').style.display==='none'?'':'none'">显示/隐藏区域</button>
<main><svg viewBox="0 0 {width} {height}"><image href="data:{mime};base64,{encoded}" width="{width}" height="{height}"/><g id="regions">{''.join(polygons)}</g></svg>
<div><table><thead><tr><th>顺序</th><th>区域</th><th>类别</th><th>内容</th><th>多边形</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></main>'''
    Path(target).write_text(page)
    overlay=Image.open(image_path).convert('RGB')
    draw=ImageDraw.Draw(overlay)
    for region in result['regions']:
        points=polygon_points(region['polygon'],width,height)
        color='#dc2626' if region['kind']=='text' else '#2563eb'
        draw.line(points+points[:1],fill=color,width=4)
        draw.text((points[0][0],max(0,points[0][1]-24)),str(region['reading_order']),fill=color,font_size=22)
    overlay.save(Path(target).with_name(Path(image_path).stem+'.overlay.jpg'),quality=94)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--ocr',type=Path,help='已有Vision OCR JSON；不提供则本地识别')
    p.add_argument('--review',type=Path,help='与图片哈希绑定的核对区域JSON')
    p.add_argument('--printed-page',type=int)
    p.add_argument('--work-dir',type=Path,default=Path('tmp/content-extraction'))
    args=p.parse_args()
    args.work_dir.mkdir(parents=True,exist_ok=True)
    if args.ocr:
        words=read_json(args.ocr)
    else:
        binary=compile_ocr(args.work_dir)
        result=subprocess.run([str(binary),str(args.image.resolve())],check=True,capture_output=True,text=True)
        words=json.loads(result.stdout)
        write_json(args.work_dir/(args.image.stem+'.ocr.json'),words)
    output=build_content(args.image,words,read_json(args.review) if args.review else None,args.output,args.printed_page)
    print(json.dumps(dict(image=args.image.name,size=output['image'],regions=len(output['regions']),status=output['status'],excluded=output['extraction']['excluded_counts']),ensure_ascii=False))
    return 0 if output['status']=='reviewed_sample' else 2


if __name__=='__main__':
    raise SystemExit(main())
