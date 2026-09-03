# App Schema 报告：转转

- 平台：`android`
- 包标识：`com.wuba.zhuanzhuan`
- 版本：`10.6.1`（build `10006001`）
- SHA-256：`3215646d53d5034995e937cab796b7c729328d14e12bbe2502facfab2e998287`
- 可关联到下列能力的 Scheme：`zhuanzhuan`
- 其余注册 Scheme：3 个，仅保留在 JSON 审计底稿

## 结论

找到 3 项值得继续验证的业务能力；以下已去除回调 Scheme、内部测试页和重复路由。

## 1. 搜索结果/列表：`zhuanzhuan://jump/core/searchResult/jump`

- **作用**：从第三方 App 带条件进入结果页。
- **当前判断**：已打开页面；keyword 未生效，仅适合继续 Debug。
- **处理模块**：`com.zhuanzhuan.searchresult.NativeSearchResultActivityV5`。
- **适用场景**：从识别、收藏或比价场景把用户送到目标 App 的搜索结果。

### 有用参数

| 参数 | 含义 | 入参方式 | 证据状态 |
|---|---|---|---|
| `keyword` | 搜索关键词 | 普通文本，需 URL 编码 | 真机未消费 |
| `cityId` | 城市 ID | App 内部 ID；不要默认当作行政区划码 | 仅静态候选 |
| `searchType` | 搜索类型开关 | 整数枚举；各取值语义需结合调用点或 A/B | 仅静态候选 |
| `cateId` | 商品分类 ID | App 内部分类 ID | 仅静态候选 |

### 调用示例

最短探针：`zhuanzhuan://jump/core/searchResult/jump`

已测试或完整参数示例：

```text
zhuanzhuan://jump/core/searchResult/jump?keyword=%E4%B9%90%E9%AB%98%2042171
```

### 最小复核证据

- `sources/com/zhuanzhuan/searchresult/NativeSearchResultActivityV5.java:94`（route-annotation）

### 真机结果

- ios：correct-page；page=search-input，keyboard=opened，keyword=not-consumed。用户 iPhone 真机：命中搜索框并打开输入法，但关键词为空

## 2. 搜索入口：`zhuanzhuan://jumpcore/search/jump`

- **作用**：打开目标 App 的搜索输入或目的地选择页面。
- **当前判断**：包内静态确认，尚未验证外部调用。
- **处理模块**：`仅发现包内 URL 字符串`。
- **适用场景**：作为无法可靠传入关键词时的降级入口，让用户在目标 App 内继续输入。

### 有用参数

尚未找到值得第三方调用的业务参数。

### 调用示例

最短探针：`zhuanzhuan://jumpcore/search/jump`

### 最小复核证据

- `sources/com/zhuanzhuan/homecategory/HomeCategoryActivity.java:336`（literal-url）
- `sources/com/wuba/zhuanzhuan/fragment/home/HomeCategoryFragment.java:342`（literal-url）

## 3. 搜索入口：`zhuanzhuan://jump/core/search/jump`

- **作用**：打开目标 App 的搜索输入或目的地选择页面。
- **当前判断**：包内静态确认，尚未验证外部调用。
- **处理模块**：`com.wuba.zhuanzhuan.activity.SearchActivity`。
- **适用场景**：作为无法可靠传入关键词时的降级入口，让用户在目标 App 内继续输入。

### 有用参数

| 参数 | 含义 | 入参方式 | 证据状态 |
|---|---|---|---|
| `keyword` | 搜索关键词 | 普通文本，需 URL 编码 | 仅静态候选 |

### 调用示例

最短探针：`zhuanzhuan://jump/core/search/jump`

### 最小复核证据

- `sources/com/wuba/zhuanzhuan/activity/SearchActivity.java:117`（route-annotation）
- `sources/com/wuba/zhuanzhuan/service/SearchTileService.java:71`（literal-url）

## 未展示内容

完整扫描得到 192 条路由。默认报告不展示回调、账户、订单、内部测试页及低价值重复项；需要追溯时查看同名 JSON。

## 边界

- 多个业务/回调 Scheme 共存，注解路由不能自动归属到某一个 Scheme。
- Android 路由静态存在不等于 iOS 实现；必须单独记录 iOS 真机结果。
