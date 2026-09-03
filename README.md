# App Schema Tool

一个证据优先的移动 App 自定义 URL Scheme 调查工具。它把以下层级分开记录：

1. Scheme 是否注册；
2. path 是否存在；
3. query 参数是否被代码读取；
4. 页面是否正确；
5. 参数是否被真机业务页面消费。

工具不分析 Universal Link，也不会把 Android 静态路由直接标记为 iOS 已支持。

默认交付的是少量“能力卡片”，而不是数百条反编译路由。例如一项能力会直接回答：它打开什么页面、URL 怎么写、哪些参数会改变业务结果、参数格式是什么、适合什么场景、静态证据在哪里，以及真机是否实际消费了参数。

可查看两份脱敏后的真实输出：

- [`examples/tongcheng.md`](examples/tongcheng.md)：同程酒店列表，城市和日期已生效，酒店名未生效。
- [`examples/zhuanzhuan.md`](examples/zhuanzhuan.md)：转转搜索入口可打开，但关键词未被 iOS 页面消费。

## 安装

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

扫描 APK 时需要 JADX。可以提前反编译，也可以通过 `--jadx` 指定可执行文件。

## 基本使用

确认 App 身份：

```bash
app-schema resolve "同程旅行"
```

扫描 APK：

```bash
app-schema inspect "同程旅行" \
  --artifact tongcheng.apk \
  --jadx /path/to/jadx \
  --output reports/tongcheng.json
```

如果希望日常只输入 App 名，可以维护一个经过审核的来源目录：

```bash
cp app-schema-sources.example.json app-schema-sources.json
app-schema inspect "同程旅行" --output reports/tongcheng.json
```

来源项可以使用本地 `artifact_path`，也可以使用公开下载地址 `artifact_url`。远程地址必须同时配置预先核验的 `sha256`，下载内容变化时工具会停止，不会继续分析未知包。

复用已有 JADX 目录：

```bash
app-schema inspect "转转" \
  --artifact zhuanzhuan.apk \
  --decoded zhuanzhuan-jadx \
  --output reports/zhuanzhuan.json
```

扫描 IPA：

```bash
app-schema inspect "目标 App" --artifact app.ipa --output reports/app.json
```

生成 Debug URL。默认拒绝没有静态参数消费证据的字段：

```bash
app-schema probe reports/zhuanzhuan.json \
  --route route:jump/core/searchResult/jump \
  --scheme zhuanzhuan \
  --param 'keyword=乐高 42171' \
  --param searchType=0
```

记录真机结果：

```bash
app-schema record-test reports/zhuanzhuan.json \
  --platform ios \
  --url 'zhuanzhuan://jump/core/searchResult/jump?...' \
  --outcome correct-page \
  --observed page=search-input \
  --observed keyword=not-consumed \
  --notes '搜索框获得焦点并弹出键盘'
```

每次扫描同时生成 JSON 和 Markdown：

- Markdown 是默认给人看的简洁能力报告，只展示少数高价值业务能力，每项说明作用、参数含义、入参方式、应用场景、证据和真机结果。
- JSON 是完整审计底稿，用于追溯源码、生成 URL 和追加真机记录，不直接把数百条内部路由倾倒给决策者。
- 只有明确需要人工穷举时才加 `--audit-index`，将全量路由索引附在 Markdown 末尾。

仓库还包含 `skills/app-schema-research`，可安装为 Codex Skill。Skill 负责 App 消歧、证据归并、参数语义判断、候选排序和 A/B 探针设计；CLI 负责可重复的静态扫描与结构化留证。

Skill 的协作方式是“LLM 做判断，扫描器做事实”：LLM 可以解释某个 Scheme 是 AI 助手、酒店搜索还是详情页，并设计下一组探针；但每个判断都必须回指包内静态证据或真机结果，不能根据 App 名或字段名把推测升级成已验证能力。

## 当前支持的静态证据

- Android Manifest 中声明的自定义 Scheme；
- iOS `Info.plist/CFBundleURLTypes/CFBundleURLSchemes`；
- 同程式 `@Router(project, module, visibility)`；
- 转转式 `@Route(tradeLine, pageType, action)`；
- `@RouteParam(name=...)`；
- `getQueryParameter/getStringExtra/BridgeData.c/Bundle.getString` 等参数读取；
- RouteBus 调用链中的参数与常量默认值；
- 代码、JSON、JS、资源文件中的完整自定义 Scheme URL。

## 证据边界

- “包内未找到”不代表路由不存在：路由可能由服务端下发、加密或运行时注册。
- APK 静态证据只证明 Android 包内实现，不证明 iOS 同名路由。
- `Info.plist` 只证明 iOS 注册了 Scheme，不证明具体 path/query。
- 只有真机进入正确业务页面并消费目标参数，才应标记为生产可用。
- App 名称无法唯一确定时，工具停止，不会把普通版、Pro 版或关联 App 自动合并。

## MVP 限制与下一步

当前版本不会搜索并下载来源不明的安装包。只输入 App 名完成全流程，需要先在来源目录中配置本地公开 APK/IPA，或配置经过审核且锁定 SHA-256 的公开下载地址。

后续适合增加：应用商店来源插件、更多路由框架适配器、跨版本 diff、交互式真机测试清单，以及向 Compy 输出经过验收的白名单配置。
