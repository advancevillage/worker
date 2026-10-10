# Go HTTP 与错误边界

## 请求处理

- 按资源或用例拆分 Handler，默认注入所需业务接口；简单 CRUD 使用直接 Handler，不强制 Pipeline 或四种模式组合。
- Handler 处理 HTTP 解码、协议校验与响应；业务规则放在应用服务或领域方法中，避免直接承担存储和 SDK 细节。
- 使用具体请求与结果类型，限制请求体大小，检查解码错误；身份认证、资源授权与业务校验分别落实。
- 从 `r.Context()` 传递取消与期限；超时预算覆盖整个操作，禁止下游随意换成 `context.Background()`。
- middleware 负责横切行为，明确执行顺序、短路和日志责任；恢复 panic 作为请求隔离兜底，不能替代错误处理。

## 错误契约

- 用普通 error 表达失败；调用方需要分支判断时使用 sentinel 或结构化错误，分别用 `errors.Is/As` 识别，不匹配错误字符串。
- sentinel 集中定义规则见 [集中常量](software.md#集中定义)，错误类型用 `XxxError`；包装补充操作信息，只有允许调用方识别底层错误时使用 `%w`。
- 错误在有能力处理的边界处理；下层返回必要上下文，上层负责最终记录，避免每层“记录后原样返回”。忽略清理错误需说明其无影响，重要补偿失败需记录并恢复。
- HTTP 边界按既有契约集中映射业务错误、取消、超时与内部故障；普通函数即可，不为映射器强制引入接口。
- 对外响应不泄露内部错误、凭据或 SQL；日志关联请求与 trace，保留诊断信息并脱敏。
- 常规响应先准备再提交状态与内容；已提交响应后不得再次写 JSON 错误或改变状态码。
- 业务失败用 error 表达；需要退出进程的决定留在 `main`，保证清理路径执行，不在库和 Handler 内调用 Fatal 或 Exit。

## 流式响应与验证

- 流式请求按协议提交响应；提交后失败采用协议内错误帧或终止连接，不能退回普通 JSON 错误。
- 处理客户端取消、写入与 flush 失败、慢客户端背压；单独配置流式超时，不能机械套用普通请求期限。
- 用 `httptest` 验证成功、非法输入、未授权、领域失败和依赖失败；并发或流式变更补充相应取消与关闭验证。

业务写入、重试与生命周期见 [服务设计](../server-design-principles.md)。

依据：[Google 错误处理](https://google.github.io/styleguide/go/decisions#errors)、[Uber Errors](https://github.com/uber-go/guide/blob/master/style.md#errors)、[Go Context](https://pkg.go.dev/context)。
