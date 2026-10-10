# Go 开发索引

只读取与当前任务有关的文件；编码默认规则在 software.md，系统运行规则在服务设计中。

| 任务 | 资料 |
|---|---|
| 系统架构、风格选择与跨模块边界调整 | [架构设计](../../architecture-design-skills/SKILL.md) |
| 编码、包边界、项目布局、依赖与配置 | [software.md](go-server/software.md) |
| 接口、构造、配置选项与对象所有权 | [object.md](go-server/object.md) |
| 抽象与设计模式选择 | [pattern.md](go-server/pattern.md) |
| HTTP、middleware、错误处理与流式响应 | [handler.md](go-server/handler.md) |
| 数据访问、事务、幂等重试、后台任务与退出 | [服务设计](server-design-principles.md) |

## 来源与分歧处理

统筹参考 [Google Guide](https://google.github.io/styleguide/go/guide)、[Decisions](https://google.github.io/styleguide/go/decisions)、[Best Practices](https://google.github.io/styleguide/go/best-practices) 与 [Uber Guide](https://github.com/uber-go/guide/blob/master/style.md)。语言和标准库行为以 [Go 官方评审建议](https://go.dev/wiki/CodeReviewComments)及对应版本官方文档为准。

个人约定见 [技能入口](../SKILL.md)，优先于外部指南的风格建议；以下统一选择不代表两份指南完全一致。

| 差异或工具建议 | 本技能默认选择 |
|---|---|
| Go 官方通常建议实现方返回具体类型 | 工作区业务服务和客户端默认返回职责明确的接口，详见 [对象设计](go-server/object.md) |
| Uber 为未导出全局名称加 `_`，Google 通常避免下划线 | 使用 `mixedCaps`，既有项目保持包内一致 |
| Uber 建议 99 字符软限制，Google 不设固定行长 | 不设硬限制，长表达式优先简化，避免机械换行 |
| Uber 建议其 atomic 包 | 按 Go 版本优先标准库类型化原子操作，沿用已有依赖 |
| 测试断言库 | 默认标准库 `testing`，沿用项目测试体系 |
| Lint 工具 | 使用项目已配置的工具；新配置按需选 Staticcheck 或 golangci-lint，不引入已弃用的 golint |

不要机械照搬指南中依赖特定组织、工具或旧版本的要求。新 API 和工具规则先核对项目版本；其他细节按需查看原文。
