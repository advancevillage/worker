# 服务端关键设计

按业务不变量选择方案，写明关键失败场景与取舍；不预设数据库引擎、隔离级别或分布式架构。默认时长、容量与阈值引用 [集中常量](go-server/software.md#集中定义)，运行期配置通过 Option 或既有配置体系覆盖并校验。

## 数据与可靠性

- 先确定数据约束、访问模式、容量与延迟目标，再选择存储和索引；分析负载影响在线事务时再隔离。
- 数据库查询参数化；事务边界围绕业务不变量，核对实际数据库的隔离语义，用约束、锁或原子更新解决并发冲突。
- 检查提交结果；及时关闭 rows、响应体等资源并检查相关读取错误。数据库和 HTTP 客户端复用连接，按负载设置池容量及超时。
- 外部调用超时可能已经产生副作用；只对可恢复且幂等的操作限次重试，设置总期限、退避与抖动。
- 幂等键通过唯一约束或原子状态转换持久化，并约定重复请求的结果；进程内锁不能保证跨节点幂等。
- 跨系统写入按一致性需求选择 outbox、可靠补偿或事务方案；补偿失败有重试与核对路径，不能忽略后当作已恢复。
- 缓存明确有效期、失效与允许的陈旧范围；一致性按业务选择，不对所有读取强制同一种保障。
- 消息消费者处理重复与重放，成功完成所需持久化后再确认；明确顺序要求与失败消息处理。
- Schema/API 演化保持消费者兼容，不复用旧字段语义；批任务和派生结果明确检查点、重放与重建方式。
- 分布式协调使用成熟实现；租约失效后旧持有者仍可能写入，必要时由存储端校验 fencing token 或版本。跨节点排序不直接依赖本地墙钟。

## 并发与 Context

- 需要 Context 的函数以其为首参数，调用链沿用调用方 Context 并及时 cancel；普通业务参数显式传递，Context 仅承载请求范围元数据。
- 不把请求 Context 保存到长期对象；受外部接口约束时明确例外。脱离请求的任务有独立生命周期、期限和可靠交付要求。
- 每个 goroutine 明确启动者、停止信号、错误归属和等待机制；禁止无归属的 fire-and-forget，不在 `init()` 启动任务。
- 通过 worker 数量、信号量或队列实现有界并发与背压；channel 容量来自实际需求，关闭责任由发送侧明确。
- 共享状态用锁、消息传递或原子操作保护；避免持锁执行外部 I/O，需要关联更新的状态不能只靠各字段独立原子化。

最小后台循环示例：调用方负责派生并取消 ctx，在独立 goroutine 中执行 run，通过等待其返回完成关闭；work 必须响应取消或有期限。

```go
package worker

import (
	"context"
	"time"
)

func run(ctx context.Context, interval time.Duration, work func(context.Context) error) error {
	ticker := time.NewTicker(interval) // 调用方保证 interval > 0。
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			if err := ctx.Err(); err != nil {
				return err
			}
			if err := work(ctx); err != nil {
				return err
			}
		}
	}
}
```

## 生命周期与验证

- 启动依次校验与组装，失败时释放已创建资源；关闭时停止接收工作、排空或取消在途操作、等待任务并释放资源，按依赖关系确定顺序。
- 关闭有独立总期限；HTTP Shutdown 使用仍有效的 Context，不复用已取消的信号 Context。记录超期与未完成任务。
- 观测错误率、尾延迟与资源饱和度；日志与 trace 关联，指标标签避免用户 ID 等高基数值。
- 测试业务边界与失败路径；事务、幂等和消息语义在需要时做集成验证，使用项目 Go 版本支持的测试 API。
- 并发测试包含取消与退出并检查竞态；性能优化用 benchmark、pprof 或真实负载证明收益，不能只凭经验加缓存或预分配。

错误映射与日志边界见 [HTTP 与错误](go-server/handler.md)；项目检查命令见 [技能入口](../SKILL.md)。

依据：[Google Context 与并发](https://google.github.io/styleguide/go/decisions)、[Google Best Practices](https://google.github.io/styleguide/go/best-practices)、[Uber goroutine 生命周期](https://github.com/uber-go/guide/blob/master/style.md#dont-fire-and-forget-goroutines)。数据一致性规则为工作区设计建议，按实际存储和业务契约核对。
