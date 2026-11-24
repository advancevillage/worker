# 数据与审核协议

## 最终目录

```text
{年级}/{学科}/{上下册}/
├── 教材.pdf
├── meta.json
├── image/<pid>
├── content/book.json
├── content/edurich/<pid>.json
├── content/preview/<pid>.html
└── trans/<pid>
```

pid 为最终原图字节 MD5 加实际后缀 `.png` 或 `.jpg`，例如 `a…f.png`；JSON 名为 `a…f.png.json`，HTML 为 `a…f.png.html`。译文文件复用原图 pid，不按译文自身哈希命名。meta 仅 isbn、subject、volume、publisher；ISBN 从下载文件名提取，缺失保持 null，需报告，不编造。

book.json 固定八个分类：cover 封面、preface 序言、content 目录、body 正文、afterword 后记、copyright 版权页、back_cover 封底、blank 空白页。除 body 是 `{ "课本页码": "pid" }` 外，其余均为 pid 数组；不存在的分类保留空容器。无 unknown/other。最终无物理页、序号页字段；正文页码不能靠数组位置推断。

每页 JSON 仅 `pid,width,height,areas`，可选 `trans`。areas/trans 按阅读顺序排列，每项只有 polygon 和 edurich。无 regions、region_type、role、order、status、provenance 或嵌套区域。阅读顺序由数组表达，不新增 seq。trans 是译文图对应的点读区域列表。

## 多边形

polygon 字符串 `x1:y1:x2:y2:…`，左上角(0,0)，整数原图像素；顺时针，3–512点，不重复首点、不自交、不越界（x<width，y<height）。每页合计≤20000点、每列表≤500区域。图片≤30MB/40MP，内容JSON≤10MB。

有独立底色的标题、标签，沿其外边界标注（对话框和气泡按下述实际内容规则处理），圆角按曲率取点，包含底色内边距。无底色文本按自然文字块标注；插画按可辨识的完整对象/构图轮廓。不要沿每个文字笔画描边。近似颜色区域互连、渐变或共享底色导致边界不明确时，先确认，不把全页背景当成一个区域。

坐标必须匹配最终图片；缩放、换格式或重新压缩后，重新计算哈希并核对区域。页码不作为点读内容；题号、正文数字、公式数字及页脚章节文字保留。

## EduRich 子集

每区域携带完整 `protocol,version,modules,document,assets,styles` 对象。版本 `0.1.0-draft`，styles 为 `{}`，document 使用 `profile: reflow`，节点ID在文档内唯一。

支持节点：core:paragraph、core:heading（level 1–6）、core:text、math:inline、math:block、media:image。类型体现在 EduRich 节点，不在区域外增加类型字段。语言仅 zh/en，拼音用 zh；纯图/公式可省略语言。

通过 `readalong.document()`、`paragraph()`、`add_module()` 构造文档，并用 validate_page 验证。示例：

```python
from readalong import document, paragraph, add_module
zh = document('title', 'zh')
zh['document']['body'] = [paragraph('text', '加法')]
math = document('formula')
add_module(math, 'math')
math['document']['body'] = [{'id':'sum', 'type':'math:block', 'latex':'3+1=4'}]
en = document('english', 'en')
en['document']['body'] = [paragraph('source', 'Hello'), paragraph('translation', '你好')]
```

英文区域恰好两个文本块，先英文后中文译文，这是应用约定。不是任意增加 translation 节点属性。数学支持数字、变量、运算以及 times/div/frac/sqrt/mathrm/text；不支持宏时 tell-me，不能渲染成普通源码并称为完成。

插画文档添加 media 模块，body 节点为 `{id,type:"media:image",assetId,alt,decorative:false}`。assets 的对应键值仅 `{uri:"asset:image/<pid>",mediaType:"image/png或image/jpeg",width,height}`，可指向整张源图，宿主按区域 polygon 展示局部；容器合并时将局部图标提取为 image/<图片MD5>.png 辅助图片，资源尺寸为其实际尺寸。辅助图片不进入 book.json 页列表，校验器必须验证其文件、哈希和尺寸。不增加裁剪节点，也不把块图放入 paragraph.children。一个气泡可以在同一文档的 body 中顺序保存多个文本块和图片块。

JSON Schema 位于 `scripts/schemas/`，完整运行约束由 readalong.py 和 validate_book.py 执行。

## 人工核对输入

`<源文件名去扩展>.review.json`：

```json
{"image_sha256":"源图SHA256","reviewed":false,"areas":[]}
```

areas 填写完整区域；在核对最终原图、内容、轮廓后才设置 reviewed=true。空白页必须实际确认，不能以空列表代替失败的识别。审核输入属于运行目录，最终内容不保存 reviewed 或来源记录。

译文更新输入：`{pid,reviewed:true,changes:[{polygon,source_edurich,edurich}]}`，精确匹配源 polygon 和完整源文档。

译文图审核输入：`{pid,reviewed:true,page_sha256,replacements:[{source_polygon,polygon,background_confirmed:true,background:[255,255,255],min_font:18,max_font:36}]}`。当前合成仅支持已确认纯色矩形遮罩，需覆盖原英文且中文不溢出；复杂背景应确认其他处理方式。render_translation.py 需要本地中文字体路径，生成 trans/<pid> 并补充页JSON的trans区域。

对话框、对话气泡和思考气泡只标注实际内容区域：连续多行文字按自然文本块圈选，保留少量阅读内边距，不逐字描边；排除大块空白底色、外框、尾巴及分离尾圈，不为这些装饰单独建area。气泡内有教学意义的图标按实际内容保留，仅在语义连续且不会包入大块空白时与文字合并，不能仅因共用气泡而合并。 题号圆圈独立；不同语义块不按距离或颜色自动合并。

单个polygon不能表达分离部件或内部孔洞。气泡装饰尾圈直接不建区域；确有教学意义的分离对象按各自内容标注，不以凸包、细桥或放大多边形连接空白。需要保留真实孔洞或用户明确要求整体外形点击时，应先检查现有协议能否表达，不能伪造拓扑。具体边界与验收见[轮廓与视觉验收](contour-quality.md)。
