# 分步操作

以下从已安装技能的 `scripts/` 目录运行。命令中的书籍资源 ID、样本页码和路径应由实际文件确定，不能照搬历史样本。参数详情用各脚本 `--help`。

## 环境

Python 3.11+，依赖见 `scripts/requirements.txt`；Node.js 用于生成数学预览。macOS 需 Chrome 与 Xcode Command Line Tools（swiftc/Apple Vision）。不支持的系统不要直接运行 OCR 步骤。

```sh
TEXTBOOK_WORK="$HOME/Library/Caches/smartedu"
mkdir -p "$TEXTBOOK_WORK"
python3 -m venv "$TEXTBOOK_WORK/venv"
"$TEXTBOOK_WORK/venv/bin/python" -m pip install -r requirements.txt
PY="$TEXTBOOK_WORK/venv/bin/python"
```

已有合适虚拟环境可复用，不要求每次安装依赖。浏览器 profile 和 cookies 位于运行目录，不能进入交付包或日志。

## 1. 下载

```sh
"$PY" download_pdf.py --subject 数学 --grade 一年级 --version 人教版 \
  --volume 上册 --work-dir "$TEXTBOOK_WORK/download"
```

先查询实际目录候选；不确定的版本/年度须确认。下载器使用可见 Chrome，等待用户登录及 PDF.js 阅读器加载，再调用阅读器 getData 获取完整 PDF。不能把动画 PNG 或网页请求当作教材下载。生成 books.json，各资源目录有 download.json/source.pdf。下载后校验 PDF 可打开、页数和哈希。

可用 `--browser-profile PATH` 复用已有独立登录；用户明确授权导入 Cookie 时使用 `--cookies-file PATH`（仅本人可读的 Cookie JSON），不把 token 写在命令行或技能内。登录等待超时后保留状态，用户登录完成再重跑。

## 2. PNG 与页码

从 books.json 取得单册绝对路径，记为 TEXTBOOK_BOOK。使用暂存归档承接命名图片，最终输出另建目录。

```sh
"$PY" render_pdf.py --book-dir "$TEXTBOOK_BOOK" --dpi 300 --format png
"$PY" identify_pages.py --book-dir "$TEXTBOOK_BOOK"
```

检查 mapping.json 和 review.html。分类允许封面、序言、目录、正文、后记、版权页、封底、空白页。异常需查看对应页后修正 category/printed_page/issues 并确认 reviewed；不能机械清空问题列表。正文页码由印刷数字确定，不按 PDF 序号或固定偏移猜测。重复页码等不能通过 reviewed 绕过。

```sh
"$PY" organize_book.py --book-dir "$TEXTBOOK_BOOK" --output "$TEXTBOOK_WORK/archive"
```

archive.json 指向命名图片目录，如 image/封面-01.png、image/24.png。这是处理中间目录，最终扁平目录采用 pid。

## 3. 两轮压缩

```sh
"$PY" compress_images.py --work-dir "$TEXTBOOK_WORK/download" \
  --book-dir "$TEXTBOOK_BOOK" --files 封面-01.png 24.png --tabs 2
```

样本名按实际映射选取，整书时省略 --files。一张图片在同一 tab 完成两轮，不重复打开浏览器窗口；tabs 默认3，可设1–5。每轮必须观察实际上传请求、下载结果，并检查真实文件格式和尺寸。TinyPNG 可能改变像素，多轮不保证更小或更清晰。

状态检查：同样参数配合 `--action status`；暂停/恢复用 pause/resume。验证码、配额或未产生真实上传时停止，保留原图和中间文件。压缩记录和 original/round-01…02 位于该册 compression/。完成两轮才替换源图片、更新 archive.json 回执并固定 pid；绝不手工伪造 compression_rounds。

## 4. 点读样本与整书

```sh
"$PY" flat_pipeline.py --book-dir "$TEXTBOOK_BOOK" \
  --output "$TEXTBOOK_WORK/sample-output" --work-dir "$TEXTBOOK_WORK/flat-work" \
  --images 封面-01.png 24.png --review-dir "$TEXTBOOK_WORK/reviews"
```

review-dir 中为 `{源文件名去后缀}.review.json`，格式见协议参考。缺少审核文件会生成 OCR 草稿并 tell-me；查看原图补全插画、多边形、文本与公式，确认后重跑。自动识别不是完整语义分割。

英文区域需同时包含原文和中文译文，还必须生成关联中文译文图才能完成校验。当前 flat_pipeline 不自动串联翻译：英文流程使用 build_book_index.py → extract_flat.py → translate_content.py（需要时）→ render_translation.py → validate_book.py 分步完成，分别读 `--help`。候选索引在工作目录 candidate-book.json，逐页任务在 jobs.json。

全书省略 --images，必须保证每页通过校验；完整输出包含教材.pdf。--output 指向最终册目录，--work-dir 与输出互不包含且位于同一文件系统（发布采用 rename）。不得与仍在压缩的命名归档重叠。

## 5. 校验与发布

`validate_book.py --root OUTPUT` 验证索引、pid/真实格式/尺寸、每页区域、资源引用和翻译图，并生成预览。候选索引用 `--candidate PATH`，全部通过后才发布 content/book.json。

打开 content/preview/<pid>.html：检查左图适合窗口、右侧 pid/尺寸、每区域坐标直接展示、插画和公式排版、边界点击对应卡片、正文页码跳转。使用正常桌面窗口（如1440×900），截图不截成超长整页。逐页审核文本与轮廓，检查页码未混入点读内容。

flat_pipeline 会保留替换输出的备份和发布日志。只更新已有整书的样本时，应先备份旧 image/content，再有选择地合并文件与 book.json 的对应条目；不得用只含样本的索引丢弃其他页。单纯发布两页样本需明确标为样本。

## 迁移与预览

重新从 PDF 生成 PNG 后，再完成压缩，使用：

```sh
"$PY" migrate_page.py --old OLD_PAGE_JSON --image NEW_PNG --output NEW_REVIEW_JSON
```

迁移按实际宽高缩放多边形，更新图片资产和哈希，产出 reviewed=false。叠图核对后确认，重建索引/内容/预览；不能直接改旧 pid 后缀。旧无后缀 JPEG pid 仅保留读取兼容，新输出必须带后缀。

预览模板在 preview_content.py；tools/render_math.cjs 使用随包 KaTeX 0.16.22 输出 MathML，打开 HTML 无需 CDN。图片左侧适合窗口、可缩放；右侧区域独立滚动，坐标常显，插画预览限高200px。

## 带底色或描边的区域

仅对确需完整外形的标题底板或教学图示使用以下工具。对话框及气泡直接按实际文字和有效图标的位置生成内容候选，不沿底色提取整泡轮廓；旧整泡区域应重新圈选内容，并删除装饰尾部区域。

使用 refine_background.py 为扁平 areas 中的单个区域提出候选：

```sh
"$PY" refine_background.py --image FINAL_PNG --page PAGE_JSON --area 1 \
  --roi 600 160 1570 380 --seed 1000 200 --output CANDIDATE_REVIEW_JSON
```

area 是零起始数组位置；roi 为 x0 y0 x1 y1、seed 为底色或描边上的像素，均须按当前图选取，上述仅为数学样本示例。脚本以局部连通颜色提取外轮廓，忽略文字造成的内部孔洞，圆角保留合理节点；输出 reviewed=false 和叠加PNG。默认颜色容差28、简化误差1.5像素。背景连到ROI边缘、轮廓未包住原文字或几何非法时停下确认。共享底色的多块文字不应逐块套用同一个大轮廓；渐变、断裂边框和复杂纹理需另行核对。旧 refine_regions.py 仍仅是特定蓝/暖色分界辅助，不当作通用工具。

核对候选边界和内容后才设置 reviewed=true，提取并更新对应页JSON和预览。原图未变化时pid保持不变，无需重新压缩。

## 确需完整外形的教学容器合并

此流程仅用于已确认需要整块教学容器的情况，或用户明确要求外形点击；不作为对话气泡的默认处理流程。连续气泡文本可合并EduRich内容，但坐标仍按内容重新确定。

`merge_areas.py --image FINAL_PNG --page PAGE_JSON --areas 9 10 11 12 --connected-container-confirmed --roi 310 1940 820 2320 --seed 400 2000 --tolerance 10 --output REVIEW_DIR/24.review.json` 为示例；所有索引与坐标必须据当前原图选择。使用零起始、连续、按阅读顺序的areas索引。

脚本提取容器闭合外边界，检查包住全部选中内容，合并文档、重命名节点ID并保留文本/标点。原图标裁成小PNG存入审核目录image/，由extract_flat.py在重建时校验复制到输出image/。审核JSON与这些辅助图片必须一起保存。不得把图标重新识别成文字，不得沿用整个容器作为图标裁剪区域。

输出reviewed=false；核对对象范围、阅读顺序和预览后才能确认。气泡装饰尾部及尾圈不建区域；内容选取和空白处点击检查按[轮廓与视觉验收](contour-quality.md)执行。原图不变则页面pid不变；新增辅助图按自身MD5命名。当前EduRich草案只支持块图，预览按语义顺序显示文本块与图片块，不伪造行内图片节点。

压缩轮数默认2，可用`--rounds N`指定。旧任务保留原目标；显式变更用`--action set-rounds --rounds 2`，保留历史与备份，复用真实第2轮产物。迁移不解除暂停；限流解除后显式resume再run。旧五轮已发布资源无需回退。

## 轮廓质量修正

按[轮廓与视觉验收](contour-quality.md)分别验收几何、内容、视觉与交互。现有refine_background.propose要求新候选包住整个旧区域，仅适合旧文字框扩展；旧轮廓已圈入背景、需要收缩时不能直接沿用该约束。可提交逐点核对的新审核候选；使用`--mode replace --protected PATH`可生成收缩/替换候选；protected JSON须含最终原图image_sha256、confirmed:true和必保内容polygons列表。仍需人工核对候选。默认enclose模式保持原行为。

`contour_review.py`提供自适应贝塞尔细分、整数化自交边诊断、分离部件候选和原图/前后线框审核材料。证据初始仅几何通过，内容、视觉、交互为pending。merge_areas新增`--connected-container-confirmed`，只在实际核对连通容器后使用。
