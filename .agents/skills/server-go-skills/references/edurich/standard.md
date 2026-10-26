# EduRich 标准与约定

版本：0.1.0-draft。本文“必须”是本草案的规范约束，“应”是允许说明理由后调整的建议，“可”是可选能力。候选能力不构成实现承诺。

## 1. 定位和模块边界

EduRich 表达教材内容、阅读顺序和排版约束，不定义业务后端、题库数据库、公式计算、答案判定或编辑器实现。

| 模块 | 职责 | 状态 |
| --- | --- | --- |
| core | 文档、段落、文本、标识、诊断与兼容 | 草案基础 |
| math | 行内与块级数学、数量及单位显示 | 草案基础 |
| media | 图片资源、图注、替代文本 | 草案基础 |
| layout | 响应式行列、尺寸、溢出 | 草案基础 |
| table / question | 表格、题干、选项、填空语义 | 候选 |
| annotation / geometry | 叠加标注、几何描述 | 候选 |
| interaction / pagination | 行为、分页与固定页面 | 候选 |

core 不依赖学科模块；模块只能依赖 core 或显式声明的模块。布局只组合块节点，不解释公式内部结构。交互通过节点 ID 引用内容，不依赖组件对象。样式、语义与布局分别定义，禁止任意字段袋充当隐含扩展。

## 2. 交换模型

规范载体为 UTF-8 JSON；重复对象键、非有限数值和重复 ID 必须报错。数组顺序是阅读顺序，JSON 对象键顺序无语义。不得静默裁剪文本或改写 Unicode；正文空白由段落规则解释。

| 根字段 | 类型与约束 |
| --- | --- |
| protocol | 字符串，固定 edurich |
| version | 字符串，当前固定 0.1.0-draft |
| modules | 对象，模块名映射到 `{version, required}`；core 必须 required=true |
| document | 对象，含 id、metadata、profile、body |
| assets | 资源 ID 到资源描述的对象，默认空对象 |
| styles | 命名样式对象，默认空对象 |

模块 version 在本草案固定 0.1.0-draft；无范围表达式。使用的模块必须声明。document.id 必须是非空字符串；metadata 默认空对象，可包含 title、language（如 zh-CN）、subject 字符串。profile 当前只能为 reflow，缺省为 reflow；不得将 fixed 当成已支持能力。body 为块节点数组，可为空。

每个节点必须有 type 和文档内唯一的非空 id；资源 ID 与节点 ID 使用独立命名空间。结构引用必须存在，树不得形成环或通过重复 ID 复用同一节点。ID 应跨内容编辑保持稳定；复制节点必须分配新 ID。

## 3. 节点与合法位置

内置节点采用模块前缀，避免后续模块冲突。不再并存 math/equation、row/layout 等多种同义形式。

| type | 类别 | 专属字段与约束 |
| --- | --- | --- |
| core:paragraph | 块 | children：行内节点数组，可空 |
| core:heading | 块 | level：1—6 整数；children：非空行内数组 |
| core:text | 行内 | value：字符串；marks：可选的 bold、italic、underline 枚举数组 |
| math:inline | 行内 | latex：非空字符串；spoken：可选的纯文本朗读替代 |
| math:block | 块 | latex、spoken 同上；align：start/center/end，默认 center |
| math:quantity | 行内 | value：十进制字符串；unit：非空字符串 |
| media:image | 块 | assetId：资源 ID；alt：字符串；decorative：布尔值，默认 false |
| media:figure | 块 | image：单个 media:image；caption：行内节点数组，默认空 |
| layout:row | 块 | children：非空块数组；gap、minItemWidth 见布局规则 |
| layout:column | 块 | children：非空块数组；gap 见布局规则 |

document.body、row.children、column.children 只接收块节点；paragraph/heading/caption 只接收行内节点。行内图片暂不纳入基础草案，禁止将块图塞入文字段落。题号、答案和选项暂不以普通文本约定冒充已标准化题型节点。

所有节点可有 styleRef 字符串和 style 对象；只有块节点可有 layout 对象。除扩展机制声明的属性外，未知字段产生诊断；严格校验视为错误，不静默解释拼写错误。

## 4. 文本、样式与数学

core:text 是普通 Unicode 文本，不解析 Markdown、HTML 或美元公式分隔符。换行字元按空格呈现；新段落用独立 paragraph，强制行内换行列为待决能力。不 trim 首尾空格；布局负责普通空格折行，保留空白排版需未来明确能力。

style 可用字段：fontSize（正逻辑单位，默认 16）、fontFamily（字体角色 body/heading，默认 body）、color（#RRGGBB，默认 #222222）、lineHeight（正倍率，默认 1.5）。文档根默认样式暂由渲染配置提供，必须在验收报告记录。命名样式不得继承其他命名样式；合并顺序为基础默认、父文本样式、styleRef、节点 style。只继承这四个文本字段；布局、边框与背景不隐式继承。marks 表达强调，不改变正文含义。禁止直接复制 CSS 或 Flutter 属性。

latex 仅表达数学，不含 $、$$ 或外层数学环境分隔符。首期共同语法限定为变量、数字、加减等号及 `\times`、`\div`、`\frac`、`\sqrt`、上下标、`\mathrm`、`\text` 的简单用法；具体命令与参数边界仍需兼容清单验证。禁止任意宏定义、外部资源命令、HTML 注入和执行能力。中文优先置于 text；必须出现在公式内的中文使用 `\text{}`，其字体支持单独验收。

math:inline 是不可拆分行内盒，按数学基线与正文对齐；行高必须容纳上下伸出部分，不能裁切分数。公式不得按字符串字符强制断行。过宽公式在交互屏幕中水平滚动并产生溢出诊断；静态导出无法滚动时必须报告错误，不静默缩小。复杂方程组、矩阵、化学式和竖式不属于已确认交集。

quantity.value 用十进制字符串保留精度，允许负号、小数，不允许指数表达式；unit 按大小写保留，如 cm、cm²、kg、km/h、°、℃。显示数字与单位之间使用不可断窄空格，°、℃直接连接。value 与 unit 是显示的唯一来源，不另存一份可冲突 latex。本草案不赋予单位换算语义，不将任意字母自动识别成单位。将来单位注册表与换算另立版本。

## 5. 布局与跨端契约

逻辑单位 u 对应 Web CSS px 和 Flutter logical pixel，不是物理像素。正文随用户字号设置等比缩放；不得以固定高度裁切文字。

块 layout 可含 width（非负 u 或 0%—100% 字符串）、maxWidth（正 u）、align（start/center/end，默认 start）；宽度未给出时占可用宽度，图片默认最多占可用宽度并保持原比例。宽度百分比相对父容器内容宽度；maxWidth 在 width 之后限制。尺寸规则不推导像素级字体一致性。

row.gap、column.gap 是非负 u，默认 12。row.minItemWidth 是正 u，默认 240。row 中项目等分可用宽度；若 `(可用宽度 - gap×(项目数-1))/项目数 < minItemWidth`，整行切换为一列，子项阅读顺序不变；不进行逐项流式折行。column 子项纵向排列。当前不支持固定列宽、任意 flex、stack、图文环绕或绝对定位。

排版不得重排语义树、裁掉正文或让图片改变阅读顺序。中文禁则、标点挤压和英文断词需后续专项标准；当前不声称完整教材复刻。分页与固定画布另设 profile，不能与 reflow 约定混用。

## 6. 资源与图片

资源描述必须含 uri、mediaType、width、height；尺寸为正整数，表示方向纠正后的原始像素大小。可选 digest 为内容校验摘要，算法名和编码需配套声明。uri 可为 HTTPS 地址或受控的 asset: 引用，由宿主映射；正文节点只引用 assetId。禁止脚本 URI 和任意本地文件访问。离线导出必须解析全部资源并记录缺失项。

image 采用 contain，保留原图比例；首期不裁剪，因此无歧义的标注映射优先于 cover。非装饰图 alt 必须非空；decorative=true 时 alt 必须为空。figure 图注不会替代图片 alt。资源缺失时显示保留比例的占位与 alt，产生 E_ASSET_MISSING；严格导出视为失败。

候选 annotation 模块统一原点为方向纠正后原图左上角，x/y/width/height 取 [0,1]；矩形必须在图内。坐标映射到 contain 实际图像矩形，排除留白；若未来支持裁剪必须同时定义裁剪与标注变换。该坐标约定尚不定义可用的标注节点。

## 7. 扩展、版本和降级

核心节点保留 core/math/media/layout 命名空间；第三方使用反向域名命名空间，例如 org.example:abacus。扩展必须登记模块版本、依赖、合法位置和字段约束，不能覆盖内置语义。

每个节点可有 fallback：与原节点类别相同的已知节点数组；替代节点 ID 同样全局唯一，fallback 不可嵌套。未知必需模块或节点必须停止合规渲染并报错，即使有 fallback；未知可选模块节点有 fallback 时使用替代，无 fallback 时显示明确占位并诊断，禁止静默丢失教材内容。已知节点渲染失败也不得隐瞒。

草案版本按精确匹配处理，变更不保证向后兼容。未来正式版采用 major.minor.patch：破坏语义或必需字段为 major；可协商的可选能力为 minor；不改变解释的勘误为 patch。不得仅凭主版本相同宣称支持。渲染器必须公布支持的 core、模块版本、profile 与数学能力清单。

validate、migrate、render 是独立职责；渲染不得暗中迁移原文。迁移应输出新文档及变更诊断，保留稳定 ID 或提供映射。

## 8. 校验、错误与运行约束

先结构与字段校验，再引用和模块依赖校验，再能力校验，最后渲染。诊断至少含 code、severity（error/warning）、path（JSON Pointer）、message；能定位节点时附 nodeId。不得把完整题目或答案默认写入远程日志。

基础错误码：E_VERSION、E_FIELD、E_NODE_POSITION、E_DUPLICATE_ID、E_REFERENCE、E_MODULE_REQUIRED、E_MATH_PARSE、E_ASSET_MISSING、E_LIMIT；警告码 W_FALLBACK、W_OVERFLOW。严格模式遇 error 不产出标为合规的结果；预览模式可以局部占位，但必须返回全部已知诊断。

实现必须声明输入字节、树深度、节点数量、图片解码尺寸与公式复杂度限制及超限行为；具体数值由后续能力档案确定，当前不宣称无限支持。渲染器不能执行文档提供的脚本。交互事件、答案隔离和状态持久化尚未定义，不应把正确答案放进默认公开文档扩展字段。
