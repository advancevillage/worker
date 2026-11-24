#!/usr/bin/env python3
"""Compact offline two-pane viewer with native MathML produced by local KaTeX."""
import argparse
import html
import json
import subprocess
from pathlib import Path
from readalong import read, polygon_points, image_name, validate_page, asset_name

CSS='''
*{box-sizing:border-box}html,body{margin:0;height:100%;font:15px/1.5 system-ui,-apple-system,sans-serif;color:#253044;background:#eef1f5}
.workspace{max-width:1600px;height:100dvh;margin:auto;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(340px,1fr);gap:16px;padding:16px}
.viewer{min-width:0;min-height:0;display:flex;flex-direction:column;background:#dde3eb;border-radius:12px;overflow:hidden}
.image-tools{display:flex;justify-content:center;gap:8px;padding:8px;background:#fff;border-bottom:1px solid #dde3eb}
.canvas{flex:1;min-height:0;overflow:auto;padding:8px;display:flex;align-items:flex-start;justify-content:flex-start}
.sheet{margin:auto;background:white;flex:none;display:block;box-shadow:0 1px 8px #16283b26}
.sheet polygon{fill:transparent;stroke:#3975dc;stroke-width:1.5;vector-effect:non-scaling-stroke;cursor:pointer}
.sheet polygon:hover,.sheet polygon:focus,.sheet polygon.selected{fill:#3b82f620;stroke:#174bb0;stroke-width:2.5;outline:none}
.sidebar{min-width:0;min-height:0;display:flex;flex-direction:column;background:white;border-radius:12px;overflow:hidden}
.meta{padding:16px;border-bottom:1px solid #e0e6ee}.pid{font:13px ui-monospace,monospace;overflow-wrap:anywhere;color:#536176;margin-bottom:4px}.dimensions{font-weight:650;font-size:17px}
.controls{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}button,select,input{font:inherit;padding:6px 10px;border:1px solid #c8d1dc;border-radius:6px;background:white;color:inherit}button{cursor:pointer}button:hover{background:#eef5ff}input{width:110px}#notice{color:#b42318;min-height:0;margin:6px 0 0;font-size:13px}
.cards{overflow:auto;min-height:0;padding:12px;scroll-behavior:smooth}article{padding:14px;margin-bottom:10px;border:1px solid #e0e6ee;border-radius:8px;cursor:pointer}article.selected{border-color:#3975dc;box-shadow:0 0 0 1px #3975dc;background:#f7faff}.area-title{font-weight:650;font-size:14px}.coordinates{display:block;margin:8px 0 12px;padding:8px;background:#f3f5f8;font:12px/1.5 ui-monospace,monospace;overflow-wrap:anywhere;color:#536176}
.rich p{margin:8px 0}.rich h2{font-size:20px;margin:8px 0}.rich h3{font-size:18px;margin:8px 0}.rich .formula{overflow:auto;font-size:22px;padding:10px 0}.rich math{font-family:math}.illustration{display:block;max-height:200px;max-width:100%;width:auto;margin:8px auto;cursor:zoom-in}.asset-image{object-fit:contain}.alt{font-size:13px;color:#536176}dialog{max-width:90vw;max-height:90vh;border:0;border-radius:12px;padding:16px}dialog svg,dialog img{display:block;max-height:75vh;max-width:85vw;margin:auto}dialog::backdrop{background:#17233499}[hidden]{display:none!important}
@media(max-width:760px){.workspace{height:100dvh;grid-template-columns:1fr;grid-template-rows:48% minmax(0,1fr);padding:8px;gap:8px}.meta{padding:10px}.dimensions{font-size:15px}.controls{margin-top:6px}.cards{padding:8px}}
'''
JS='''
let mode='areas', zoom=1;
const canvas=document.querySelector('.canvas'),sheet=()=>document.querySelector('.sheet:not([hidden])');
function fit(){const s=sheet();if(!s)return;const availableW=canvas.clientWidth-16,availableH=canvas.clientHeight-16;const scale=Math.min(availableW/W,availableH/H)*zoom;s.style.width=(W*scale)+'px';s.style.height=(H*scale)+'px';}
new ResizeObserver(fit).observe(canvas);fit();
document.querySelector('#zoom-in').onclick=()=>{zoom=Math.min(4,zoom*1.25);fit();};document.querySelector('#zoom-out').onclick=()=>{zoom=Math.max(.5,zoom/1.25);fit();};document.querySelector('#fit').onclick=()=>{zoom=1;fit();canvas.scrollTo(0,0);};
function selectArea(id,scrollCard){document.querySelectorAll('.selected').forEach(e=>e.classList.remove('selected'));const card=document.getElementById(id),poly=document.querySelector('polygon[data-card="'+id+'"]');card.classList.add('selected');poly.classList.add('selected');if(scrollCard)card.scrollIntoView({block:'nearest'});else poly.scrollIntoView({block:'nearest',inline:'nearest'});}
document.querySelectorAll('polygon[data-card]').forEach(p=>{p.onclick=()=>selectArea(p.dataset.card,true);p.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();selectArea(p.dataset.card,true);}};});document.querySelectorAll('article').forEach(c=>{c.onclick=e=>{if(!e.target.closest('.illustration'))selectArea(c.id,false);};});
document.querySelector('#overlay').onclick=()=>document.querySelectorAll('.sheet .bounds').forEach(g=>g.style.display=g.style.display==='none'?'':'none');
document.querySelector('#go').onclick=()=>{const n=document.querySelector('#page').value,p=body[n];if(p)location.href=p+'.html';else document.querySelector('#notice').textContent='课本没有该页码';};
const toggle=document.querySelector('#toggle');if(toggle)toggle.onclick=()=>{mode=mode==='areas'?'trans':'areas';document.querySelectorAll('[data-mode]').forEach(e=>e.hidden=e.dataset.mode!==mode);fit();};
const modal=document.querySelector('dialog');document.querySelectorAll('.illustration').forEach(s=>s.onclick=e=>{e.stopPropagation();const clone=s.cloneNode(true);clone.classList.remove('illustration');modal.querySelector('.enlarged').replaceChildren(clone);modal.showModal();});modal.querySelector('button').onclick=()=>modal.close();
'''


def render(root,page,index):
    root=Path(root);validate_page(page);pid=page['pid'];name=image_name(pid);w=page['width'];h=page['height']
    # Batch compilation avoids spawning a process for each formula.
    expressions=[]
    for key in ('areas','trans'):
        for area in page.get(key,[]):
            for block in area['edurich']['document']['body']:
                if block['type']=='math:block':expressions.append(dict(latex=block['latex'],block=True))
                for child in block.get('children',[]):
                    if child['type']=='math:inline':expressions.append(dict(latex=child['latex'],block=False))
    rendered=[]
    if expressions:
        result=subprocess.run(['node',str(Path(__file__).parent/'tools/render_math.cjs')],input=json.dumps(expressions),text=True,capture_output=True,timeout=30)
        if result.returncode:raise ValueError('EduRich math rendering failed: '+result.stderr[:300])
        rendered=json.loads(result.stdout)
    maths=iter(rendered)
    sheets=[];panels=[]
    for key,folder in [('areas','image'),('trans','trans')]:
        if key=='trans' and not (root/'trans'/name).exists():continue
        shapes=[];cards=[]
        for i,area in enumerate(page.get(key,[])):
            points=polygon_points(area['polygon'],w,h);poly=' '.join(f'{x},{y}' for x,y in points)
            shapes.append(f'<polygon tabindex="0" aria-label="区域 {i+1}" data-card="{key}-{i}" points="{poly}"/>')
            parts=[]
            for n in area['edurich']['document']['body']:
                if n['type']=='math:block':parts.append('<div class="formula">'+next(maths)+'</div>')
                elif n['type']=='media:image':
                    asset=area['edurich']['assets'][n['assetId']];asset_file=asset_name(asset)
                    if asset_file!=name:
                        aw=asset['width'];ah=asset['height']
                        parts.append(f'<img class="illustration asset-image" src="../../image/{asset_file}" width="{aw}" height="{ah}" alt="{html.escape(n["alt"],quote=True)}">')
                        continue
                    x=min(x for x,y in points);y=min(y for x,y in points);cw=max(px for px,py in points)-x;ch=max(py for px,py in points)-y
                    parts.append(f'<svg class="illustration" viewBox="{x} {y} {cw} {ch}" width="{cw}" height="{ch}"><defs><clipPath id="clip-{key}-{i}"><polygon points="{poly}"/></clipPath></defs><image href="../../{folder}/{name}" width="{w}" height="{h}" clip-path="url(#clip-{key}-{i})"/></svg><p class="alt">{html.escape(n["alt"])}</p>')
                else:
                    text=''.join(next(maths) if c['type']=='math:inline' else html.escape(c['value']) for c in n['children'])
                    tag='h'+str(min(6,n['level']+1)) if n['type']=='core:heading' else 'p'
                    parts.append(f'<{tag}>{text}</{tag}>')
            cards.append(f'<article id="{key}-{i}"><div class="area-title">区域 {i+1}</div><code class="coordinates">{area["polygon"]}</code><div class="rich">'+''.join(parts)+'</div></article>')
        hidden=' hidden' if key=='trans' else ''
        sheets.append(f'<svg class="sheet" data-mode="{key}"{hidden} viewBox="0 0 {w} {h}"><image href="../../{folder}/{name}" width="{w}" height="{h}"/><g class="bounds">'+''.join(shapes)+'</g></svg>')
        panels.append(f'<div data-mode="{key}"{hidden}>'+''.join(cards)+'</div>')
    names={'cover':'封面','preface':'序言','content':'目录','body':'正文','afterword':'后记','copyright':'版权页','back_cover':'封底','blank':'空白页'}
    options=[]
    for category,items in index.items():
        for label,target in (items.items() if isinstance(items,dict) else enumerate(items,1)):
            options.append(f'<option value="{target}.html" {"selected" if target==pid else ""}>{names[category]} {label}</option>')
    html_doc='<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>教材点读预览</title><style>'+CSS+'</style>'
    html_doc+='<main class="workspace"><div class="viewer"><div class="image-tools"><button id="zoom-out" aria-label="缩小">−</button><button id="fit">适合窗口</button><button id="zoom-in" aria-label="放大">＋</button></div><div class="canvas">'+''.join(sheets)+'</div></div>'
    html_doc+=f'<aside class="sidebar"><header class="meta"><div class="pid">{pid}</div><div class="dimensions">{w} × {h}</div><div class="controls"><select aria-label="页面" onchange="location.href=this.value">'+''.join(options)+'</select><input id="page" type="number" min="1" placeholder="课本页码"><button id="go">查看</button><button id="overlay">边界</button>'
    if len(sheets)>1:html_doc+='<button id="toggle">原图 / 译文</button>'
    html_doc+='</div><p id="notice" role="status"></p></header><div class="cards">'+''.join(panels)+'</div></aside></main><dialog><button>关闭</button><div class="enlarged"></div></dialog>'
    html_doc+=f'<script>const W={w},H={h},body='+json.dumps(index['body'])+';'+JS+'</script></html>'
    target=root/'content/preview'/f'{pid}.html';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(html_doc)
    return target

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--pid',required=True);a=p.parse_args()
    render(a.root,read(a.root/'content/edurich'/f'{a.pid}.json'),read(a.root/'content/book.json'))
