# App Schema 报告：同程旅行

- 平台：`android`
- 包标识：`com.tongcheng.android`
- 版本：`11.4.5`（build `770`）
- SHA-256：`85c0b06abc5461ad7ee6590f47fc84c73921897c038ec9d329f2f9f02a7cd2d6`
- 可关联到下列能力的 Scheme：`tctclient`
- 其余注册 Scheme：6 个，仅保留在 JSON 审计底稿

## 结论

找到 3 项值得继续验证的业务能力；以下已去除回调 Scheme、内部测试页和重复路由。

## 1. 搜索结果/列表：`tctclient://hotel/list`

- **作用**：从第三方 App 带条件进入结果页。
- **当前判断**：已进入目标页面；city, dates 生效；hotelName 未生效，仅适合继续 Debug。
- **处理模块**：`com.tcel.module.hotel.route.interceptor.HotelSearchManualTarget`。
- **适用场景**：从行程、日历或比价工具带入目的地和日期，减少在酒店 App 内重复填写。

### 有用参数

| 参数 | 含义 | 入参方式 | 证据状态 |
|---|---|---|---|
| `hotelName` | 酒店名或酒店关键词 | 普通文本，是否作为搜索词必须真机确认 | 真机未消费 |
| `tagname` | 筛选标签或目的地关键词 | 普通文本，具体实体类型需 A/B | 仅静态候选 |
| `tagName` | 筛选标签名称 | 普通文本，具体实体类型需 A/B | 仅静态候选 |
| `poiName` | 兴趣点名称 | 通常需与对应 POI ID/类型配套 | 仅静态候选 |
| `cityId` | 城市 ID | App 内部 ID；不要默认当作行政区划码 | 真机已消费 |
| `cityName` | 目的地城市名称 | 普通文本，通常与 cityId 配套 | 真机已消费 |
| `checkInDate` | 入住日期 | YYYY-MM-DD | 真机已消费 |
| `checkOutDate` | 离店日期 | YYYY-MM-DD | 真机已消费 |

### 调用示例

最短探针：`tctclient://hotel/list`

已测试或完整参数示例：

```text
tctclient://hotel/list?cityId=53&cityName=%E5%8C%97%E4%BA%AC&checkInDate=2026-09-10&checkOutDate=2026-09-12&hotelName=%E5%8C%97%E4%BA%AC%E7%8E%8B%E5%BA%9C%E4%BA%95%E5%B8%8C%E5%B0%94%E9%A1%BF%E9%85%92%E5%BA%97
```

### 最小复核证据

- `sources/com/tcel/module/hotel/route/interceptor/HotelSearchManualTarget.java:67`（router-annotation）
- `resources/assets/homepage/1068/home_module_green_a.json:1`（literal-url）

### 真机结果

- ios：correct-page；page=hotel-search，city=consumed，dates=consumed，hotelName=not-consumed。用户 iPhone 真机：进入酒店搜索页，北京和日期正确，酒店名为空

## 2. 搜索入口：`tctclient://strategy/searchDestination`

- **作用**：打开目标 App 的搜索输入或目的地选择页面。
- **当前判断**：包内静态确认，尚未验证外部调用。
- **处理模块**：`com.tongcheng.android.project.guide.activity.GuideDestinationSearchActivity`。
- **适用场景**：作为无法可靠传入关键词时的降级入口，让用户在目标 App 内继续输入。

### 有用参数

尚未找到值得第三方调用的业务参数。

### 调用示例

最短探针：`tctclient://strategy/searchDestination`

### 最小复核证据

- `sources/com/tongcheng/android/project/guide/activity/GuideDestinationSearchActivity.java:66`（router-annotation）
- `sources/com/tongcheng/android/project/guide/constant/TravelGuide.java:28`（literal-url）

## 3. 酒店频道首页：`tctclient://hotel/home`

- **作用**：进入酒店业务模块，再由用户手动搜索。
- **当前判断**：包内静态确认，尚未验证外部调用。
- **处理模块**：`com.tcel.module.hotel.route.HotelHomeManualTarget`。
- **适用场景**：作为酒店直搜失败时的业务频道降级入口。

### 有用参数

| 参数 | 含义 | 入参方式 | 证据状态 |
|---|---|---|---|
| `cityId` | 城市 ID | App 内部 ID；不要默认当作行政区划码 | 仅静态候选 |

### 调用示例

最短探针：`tctclient://hotel/home`

### 最小复核证据

- `sources/com/tcel/module/hotel/route/HotelHomeManualTarget.java:25`（router-annotation）
- `sources/com/tongcheng/android/appwidget/RecommendLoadService.java:57`（literal-url）

## 未展示内容

完整扫描得到 369 条路由。默认报告不展示回调、账户、订单、内部测试页及低价值重复项；需要追溯时查看同名 JSON。

## 边界

- 多个业务/回调 Scheme 共存，注解路由不能自动归属到某一个 Scheme。
- Android 路由静态存在不等于 iOS 实现；必须单独记录 iOS 真机结果。
