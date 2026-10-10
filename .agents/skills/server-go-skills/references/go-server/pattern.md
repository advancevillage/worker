# Go 抽象与模式选择

业务能力默认通过小接口暴露，可配置对象默认采用 Option；其他抽象在重复机制或真实变化点出现时提取，不以模式数量衡量设计。

本文件描述局部机制；pipeline、插件或事件机制涉及整体拓扑、跨模块或部署边界时，按需读取 [架构设计](../../../architecture-design-skills/SKILL.md)。局部使用某个机制不代表整个系统采用对应架构风格。

| 实际问题 | 可选机制 | 约束 |
|---|---|---|
| 业务能力封装或实现替换 | 职责明确的小接口 | 单一实现也可按个人约定返回接口，不扩大职责 |
| 日志、鉴权、限流等横切行为重复 | middleware / decorator | 顺序可解释，提前终止和错误归属明确 |
| 第三方或遗留接口与业务不一致 | adapter | 只转换协议与语义，不吞掉失败 |
| 一个用例需要调用多个依赖 | 应用服务 / facade | 只持有该用例依赖；写入一致性由事务或可靠补偿保证 |
| 多处请求处理流程稳定重复 | 类型明确的 helper，必要时 pipeline | 保留编译期检查，不统一使用 `any` 和运行时断言 |
| 对象有可选配置 | Option 接口与 With 函数 | 必填依赖显式传入，最终配置校验见 [对象设计](object.md) |
| 连接池等进程内共享资源 | 在组装处创建并注入 | 不用全局 Singleton 隐藏依赖与关闭责任 |
| 多个下游需可靠获知事件 | 持久化事件 / outbox | 进程内 Observer 不提供持久化和故障恢复保证 |

组合职责，不套用继承或“基类/子类”模型；不要提前创建 Repository、Factory、Builder 等空层。局部 `switch` 清晰且变化有限时可直接使用。

跨依赖失败、重试和补偿见 [服务设计](../server-design-principles.md)；模式不得替代这些正确性设计。

依据：[Google 简单性原则](https://google.github.io/styleguide/go/guide#simplicity)、[Google Best Practices](https://google.github.io/styleguide/go/best-practices)、[Uber Patterns](https://github.com/uber-go/guide/blob/master/style.md#patterns)。
