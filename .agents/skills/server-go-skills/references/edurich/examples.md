# EduRich 协议示例

以下是标准草案的数据示例，不是实现代码，也不代表已通过渲染验证。图片资源需由宿主提供；概念图不是该 JSON 的执行结果。

## 图文公式混排

宽度足够时图文并排；等分后任一列不足 240u 时整体转为纵向，阅读顺序保持不变。图片标签属于原图，本例不使用尚未标准化的 annotation 节点。

```json
{
  "protocol": "edurich",
  "version": "0.1.0-draft",
  "modules": {
    "core": {
      "version": "0.1.0-draft",
      "required": true
    },
    "math": {
      "version": "0.1.0-draft",
      "required": true
    },
    "media": {
      "version": "0.1.0-draft",
      "required": true
    },
    "layout": {
      "version": "0.1.0-draft",
      "required": true
    }
  },
  "assets": {
    "garden": {
      "uri": "asset:garden.png",
      "mediaType": "image/png",
      "width": 800,
      "height": 500
    }
  },
  "document": {
    "id": "lesson-area",
    "metadata": {
      "title": "长方形的面积",
      "language": "zh-CN",
      "subject": "math"
    },
    "profile": "reflow",
    "body": [
      {
        "id": "title",
        "type": "core:heading",
        "level": 1,
        "children": [
          {
            "id": "title-text",
            "type": "core:text",
            "value": "长方形的面积"
          }
        ]
      },
      {
        "id": "problem",
        "type": "core:paragraph",
        "children": [
          {
            "id": "lead",
            "type": "core:text",
            "value": "一块长方形菜地，长 "
          },
          {
            "id": "length",
            "type": "math:quantity",
            "value": "8",
            "unit": "cm"
          },
          {
            "id": "middle",
            "type": "core:text",
            "value": "，宽 "
          },
          {
            "id": "width",
            "type": "math:quantity",
            "value": "5",
            "unit": "cm"
          },
          {
            "id": "question",
            "type": "core:text",
            "value": "。它的面积是多少？"
          }
        ]
      },
      {
        "id": "diagram-row",
        "type": "layout:row",
        "gap": 16,
        "minItemWidth": 240,
        "children": [
          {
            "id": "figure",
            "type": "media:figure",
            "image": {
              "id": "garden-image",
              "type": "media:image",
              "assetId": "garden",
              "alt": "长8厘米、宽5厘米的长方形菜地"
            },
            "caption": [
              {
                "id": "caption",
                "type": "core:text",
                "value": "长方形菜地示意图"
              }
            ]
          },
          {
            "id": "explanation",
            "type": "layout:column",
            "children": [
              {
                "id": "definition",
                "type": "core:paragraph",
                "children": [
                  {
                    "id": "definition-text",
                    "type": "core:text",
                    "value": "长方形的面积等于长乘以宽。"
                  }
                ]
              },
              {
                "id": "formula",
                "type": "math:block",
                "latex": "S=8\\times 5=40\\mathrm{cm}^{2}"
              },
              {
                "id": "half",
                "type": "core:paragraph",
                "children": [
                  {
                    "id": "half-text",
                    "type": "core:text",
                    "value": "一半的面积为 "
                  },
                  {
                    "id": "half-formula",
                    "type": "math:inline",
                    "latex": "\\frac{1}{2}\\times40=20\\mathrm{cm}^{2}"
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  }
}
```

## 失败与降级案例

| 输入变化 | 预期结果 |
| --- | --- |
| length 的单位为 cm，数值为 8 | 显示 8 与 cm，中间不可断窄空格 |
| garden 资源不存在 | E_ASSET_MISSING；预览保留比例并展示替代文本 |
| math:inline 放入 body | E_NODE_POSITION |
| 重复使用 formula 的节点 ID | E_DUPLICATE_ID |
| latex 中出现未知命令 | E_MATH_PARSE 或能力不支持诊断，不吞掉题目 |
| 未知 required 模块 | E_MODULE_REQUIRED，不能标记合规渲染 |
| 可选未知节点提供同类别 fallback | 使用替代内容并产生 W_FALLBACK |
| 行内公式超宽 | 屏幕水平滚动并 W_OVERFLOW，静态导出报告错误 |

原始文字中出现 `$8$` 时必须原样显示；只有 math 节点进入数学排版。作者语法的 Markdown 转换不属于本例。
