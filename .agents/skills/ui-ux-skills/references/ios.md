---
name: ios-cartoon
description: A cartoon/illustration style design system for iOS apps.
---

## 设计语言

仅在项目采用卡通 iOS 风格时使用。以下配色、描边和阴影是风格示例；已有项目优先使用自身令牌，不直接全量替换。手势、异步状态和减少动态效果遵循 [motion.md](motion.md)。

卡通风格 iOS 设计系统的核心特征：

- **粗描边**：所有元素带 2px 深色边框，赋予插画感
- **大圆角**：按钮 pill 形，卡片 20–28px，图标容器 14px
- **鲜艳配色**：高饱和主色 + 白底页面，视觉冲击强
- **Solid Shadow**：阴影为纯色色块位移（无模糊），按压时阴影消失 + 元素位移
- **粗字重**：标题 800，正文最低 600

---

## 设计令牌 Design Tokens

```
颜色
─────────────────────────────────
Primary       #FF6B35   橙红主色
Primary Dark  #CC4A1A   主色阴影
Secondary     #4ECDC4   青绿辅色
Secondary Dark #2BA89F
Accent        #FFE66D   亮黄强调
Accent Dark   #D4B800
Success       #6BCB77 / dark #3E9A48
Danger        #FF4757 / dark #C0001A
Warning       #FFD166 / dark #B89000
Info          #74B9FF / dark #0984E3

中性
─────────────────────────────────
Black (描边)  #1A1A2E
White         #FFFEF7
BG            #FFF9F0   暖白背景
Surface       #FFFFFF
Gray 100      #F5F0E8
Gray 200      #E8E0D0
Gray 400      #B0A090
Gray 600      #6B5E52

描边
─────────────────────────────────
stroke-sm     1.5px
stroke-md     2px
stroke-lg     3px
stroke-color  #1A1A2E

圆角
─────────────────────────────────
radius-sm     8px
radius-md     14px
radius-lg     20px
radius-xl     28px
radius-pill   999px

Solid Shadow（卡通阴影）
─────────────────────────────────
shadow-sm     3px 3px 0px #1A1A2E
shadow-md     4px 4px 0px #1A1A2E
shadow-lg     6px 6px 0px #1A1A2E
按压效果：阴影消失 + translate(+4px, +4px)

间距
─────────────────────────────────
4 / 8 / 12 / 16 / 20 / 24 / 32 / 40px

字体
─────────────────────────────────
Family   SF Pro Rounded / PingFang SC
Size     xs:11 sm:13 md:15 lg:17 xl:22 2xl:28 3xl:36
Weight   heading: 800 / body: 600
```

---

## 按钮 Button

```
形态
──────────────────────────────
形状：pill（border-radius: 999px）
描边：2px solid #1A1A2E
字重：800
padding：12px 24px（MD）/ 8px 16px（SM）/ 16px 32px（LG）
阴影：solid shadow 4px 4px

变体
──────────────────────────────
Primary    bg:#FF6B35  text:white   shadow:#CC4A1A
Secondary  bg:#4ECDC4  text:white   shadow:#2BA89F
Accent     bg:#FFE66D  text:#1A1A2E shadow:#D4B800
Ghost      bg:white    text:#1A1A2E shadow:#1A1A2E（黑）
Danger     bg:#FF4757  text:white   shadow:#C0001A

状态
──────────────────────────────
Default ——> shadow 4px 4px + 正常位置
Hover   ——> 背景略亮
Press   ——> shadow 消失 + translate(4px, 4px)
Disabled——> opacity 0.45，shadow 消失，不可点

图标按钮：48×48，radius-lg(20px)，描边+shadow
```

---

## 输入框 Input

```
形态
──────────────────────────────
radius：20px
描边：2px solid #1A1A2E
bg：white
padding：12px 16px
字号：15px / weight 600
shadow：3px 3px 0px #1A1A2E

状态
──────────────────────────────
Default ——> 黑色描边 + 黑色 shadow
Focus   ——> 描边色改 Primary #FF6B35，shadow 改 Primary
Error   ——> 描边色改 Danger，shadow 改 Danger Dark
Disabled——> opacity 0.45

Label：12px 800，位于输入框上方 4px
Error Msg：11px 600 红色，位于输入框下方 4px
Search：pill 形，左侧放大镜图标，padding-left 44px
```

---

## 卡片 Card

```
形态
──────────────────────────────
radius：28px
描边：2px solid #1A1A2E
bg：white（或主题色）
padding：20px
shadow：6px 6px 0px #1A1A2E（或对应深色）

变体
──────────────────────────────
Default    白底 + 黑 shadow
Primary    bg:#FF6B35 + shadow:#CC4A1A
Secondary  bg:#4ECDC4 + shadow:#2BA89F
Accent     bg:#FFE66D + shadow:#D4B800

可点击卡片（Interactive）
──────────────────────────────
Press   ——> translate(6px, 6px) + shadow 消失

内部结构
──────────────────────────────
Header：标题（17px 800）+ 右侧操作
Body：正文（15px 600），行高 1.5
Footer：按钮/标签行，margin-top 16px
```

---

## 导航栏 Navigation Bar

```
形态
──────────────────────────────
高度：56px（标准）/ auto（大标题模式）
bg：#FFF9F0（与页面同色）
底部描边：2px solid #1A1A2E
padding：0 20px

内容
──────────────────────────────
标题：22px 800，居中
左/右图标按钮：40×40，radius 14px，2px 描边，shadow 3px 3px

大标题模式（Large Title）
──────────────────────────────
标题：36px 800，左对齐，padding-bottom 12px
```

---

## 底部标签栏 Tab Bar

```
形态
──────────────────────────────
高度：56px + safe area bottom
bg：white
顶部描边：2px solid #1A1A2E

Tab Item
──────────────────────────────
内间距：4px 16px，radius 14px
图标：24px
文字：11px 800

激活态
──────────────────────────────
bg：Primary #FF6B35
描边：1.5px solid #1A1A2E
shadow：2px 2px 0px #1A1A2E
图标+文字：白色

非激活态
──────────────────────────────
图标+文字：Gray 400 #B0A090
```

---

## 徽章与标签 Badge & Tag

```
Badge（数字角标）
──────────────────────────────
尺寸：最小 20×20，height 固定 20px
radius：pill
bg：Danger #FF4757
描边：1.5px #1A1A2E
shadow：2px 2px 0px #1A1A2E
字号：11px 800 白色

Tag（标签）
──────────────────────────────
padding：4px 10px，radius pill
描边：1.5px #1A1A2E
shadow：2px 2px 0px #1A1A2E
字号：11px 800

变体
  Primary   #FF6B35 白字
  Secondary #4ECDC4 白字
  Accent    #FFE66D 黑字
  Success   #6BCB77 白字
  Default   #F5F0E8 黑字
```

---

## 开关 Toggle

```
形态
──────────────────────────────
尺寸：54×32px
radius：pill
描边：2px solid #1A1A2E
shadow：3px 3px 0px #1A1A2E

Thumb（滑块）
──────────────────────────────
尺寸：22×22px，圆形
bg：white
描边：1.5px solid #1A1A2E
shadow：2px 2px 0px #1A1A2E
动画：cubic-bezier(0.34, 1.56, 0.64, 1)（弹性）

状态
──────────────────────────────
Off ——> bg: Gray 200，thumb 靠左
On  ——> bg: Primary #FF6B35，thumb 靠右
```

---

## 头像 Avatar

```
形态
──────────────────────────────
形状：圆形
描边：2px solid #1A1A2E
shadow：3px 3px 0px #1A1A2E
bg fallback：Gray 100，显示首字母

尺寸
──────────────────────────────
SM  32×32   字号 13px
MD  44×44   字号 16px
LG  60×60   字号 22px
XL  80×80   字号 28px

在线圆点
──────────────────────────────
12×12，Success 绿，2px white 描边，右下角
```

---

## 列表项 List Item

```
形态
──────────────────────────────
radius：28px（独立项）/ 首尾 28px（列表组）
描边：2px solid #1A1A2E
bg：white
padding：16px 20px
shadow：3px 3px 0px #1A1A2E
Press：translate(3px,3px) + shadow 消失

内部结构（左到右）
──────────────────────────────
图标容器：40×40，radius 14px，描边 1.5px，自定义背景色
内容区（flex:1）：
  标题  15px 800 #1A1A2E
  副标题 13px 600 Gray 400，mt 2px
右侧：箭头 / Badge / 开关
```

---

## 进度条 Progress Bar

```
形态
──────────────────────────────
高度：16px，radius pill
Track：Gray 200，描边 2px #1A1A2E，shadow 3px 3px
Fill：Primary 色，右侧描边 2px #1A1A2E
动画：cubic-bezier(0.34, 1.56, 0.64, 1)

可选：Fill 加斜线纹理（45° 重复渐变）增强卡通感
```

---

## 动效规范 Motion

```
缓动：cubic-bezier(0.34, 1.56, 0.64, 1)  —— 弹性/卡通感
时长：按压80ms / 恢复150ms / 状态150–200ms / 布局200–300ms；复杂演示可延至500ms，不延迟实际操作

Bounce In   : 可选角色或庆祝效果，scale 0.6→1.15→0.95→1，opacity 0→1；常规内容使用短淡入
Pop         : 可选轻微强调，scale 1→1.05→1
Wobble      : rotate 0°→-8°→7°→-4°→3°→0°
Float       : 角色可选translateY 0→-8px→0；离屏/后台暂停，减少动态效果时关闭

按压通用规则
──────────────────────────────
Down : translate(shadow offset) + shadow 消失，80ms
Up/Cancel : 恢复 translate(0,0) + shadow 出现，150ms；位移仅作用于视觉，不移动触控区
```

---

## Pencil 生成规则

在 Pencil 工具中创建 ios-cartoon 组件时：

1. **描边**：所有 frame/shape 加 `stroke: 2px #1A1A2E`
2. **Solid Shadow**：用同形状色块 offset(+4, +4) 放在底层，颜色比主色深 20%
3. **圆角**：按钮 `999`，卡片 `28`，图标框 `14`，输入框 `20`
4. **配色优先级**：橙 `#FF6B35` > 青 `#4ECDC4` > 黄 `#FFE66D`
5. **字体**：SF Pro Rounded（或 PingFang SC），标题 `800`，正文 `600`
6. **间距基础单位**：`8px`，组件间距 `16px`
