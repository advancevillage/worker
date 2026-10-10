# Go 接口与 Option 设计

以下是工作区个人默认约定；已有项目按任务范围保持兼容。

## 接口与构造

- 业务服务、领域能力和客户端默认暴露职责明确的接口，构造函数默认返回接口；DTO、配置和纯数据类型无需接口。
- 接口只包含该职责的方法，避免巨型接口；命名沿用项目约定，调用方需要更小依赖时可定义接口子集。
- 必填依赖显式传入，可选配置使用 `opts ...XXXOption` 和 `WithXXX`；设置默认值，依次覆盖，最后统一校验。
- `XXXOption` 采用带私有 `apply` 方法的接口；可复用泛型 `Option[T]`，不强制统一泛型框架。私有 apply 意味着选项由定义包提供。
- 仅初始化涉及可取消 I/O 时传入 Context；运行期方法按需接收 Context。配置无效或初始化可能失败时返回 error。

## 最小示例

客户端返回接口，Option 也是接口。必填 HTTP 客户端显式注入；示例以传入客户端的超时为默认值，`WithTimeout` 按顺序覆盖，零表示无整体超时。

```go
package client

import (
	"fmt"
	"net/http"
	"time"
)

type Client interface {
	Do(*http.Request) (*http.Response, error)
}

type ClientOption interface{ apply(*http.Client) }
type timeoutOption time.Duration

func (o timeoutOption) apply(c *http.Client)   { c.Timeout = time.Duration(o) }
func WithTimeout(d time.Duration) ClientOption { return timeoutOption(d) }

type client struct{ httpClient *http.Client }

func NewClient(base *http.Client, opts ...ClientOption) (Client, error) {
	if base == nil {
		return nil, fmt.Errorf("HTTP client is required")
	}
	cfg := *base
	for _, opt := range opts {
		if opt == nil {
			return nil, fmt.Errorf("nil client option")
		}
		opt.apply(&cfg)
	}
	if cfg.Timeout < 0 {
		return nil, fmt.Errorf("timeout must not be negative")
	}
	return &client{httpClient: &cfg}, nil
}

func (c *client) Do(r *http.Request) (*http.Response, error) {
	return c.httpClient.Do(r)
}
```

例中 Context 由请求携带；构造时不并发修改 base。复制配置保留原客户端设置但共享 Transport/Jar，调用方负责注入资源及响应体关闭；项目新客户端的默认值引用 [集中常量](software.md#集中定义)。

## 所有权

- 明确对象是否并发安全、零值是否可用、何时需要 `Close`，以及谁负责关闭注入的资源；Option 仅用于构造，不在运行中修改共享配置。
- 保存或返回 map/slice 时明确共享与可变性；需要隔离内部状态时复制，嵌套引用按契约处理，不能把浅复制当深复制。
- 公共类型优先具名持有依赖；仅在确有语义收益且愿意暴露其方法时嵌入类型。

参考：[Go 接口建议](https://go.dev/wiki/CodeReviewComments#interfaces)、[Uber Functional Options](https://github.com/uber-go/guide/blob/master/style.md#functional-options)、[Uber 数据边界](https://github.com/uber-go/guide/blob/master/style.md#copy-slices-and-maps-at-boundaries)。接口返回属于个人约定，其他正确性建议统筹参考。
