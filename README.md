# App Schema Research

**English** · [简体中文](README.zh-CN.md)

An evidence-first tool and Codex skill for investigating custom URL schemes in mobile apps. It records five questions separately:

1. Is the scheme registered?
2. Does the route path exist?
3. Does the code read the query parameter?
4. Does the URL open the expected page on a device?
5. Does that page actually use the supplied parameter?

The tool does not analyze Universal Links. Static findings from an Android app are not treated as proof of iOS support.

## What you get

The default output is a small set of capability reports. Each report explains what a URL opens, how to construct it, which parameters may affect the result, their formats and use cases, and the supporting static evidence and device observations.

Two sanitized case reports are included in Chinese:

- [Tongcheng Travel](examples/tongcheng.md): the iOS hotel page accepted the city and dates, but did not use the hotel name.
- [Zhuanzhuan](examples/zhuanzhuan.md): the iOS search page opened, but did not use the supplied keyword.

These cases document both working behavior and limitations.

## Installation

Requires Python 3.10 or later. APK scanning also requires JADX; you can reuse an existing decompiled directory or provide the executable with `--jadx`.

```bash
git clone https://github.com/fengqve/app-schema-research.git
cd app-schema-research
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Usage

The examples below retain the original Chinese app names used by the source catalog: `同程旅行` (Tongcheng Travel) and `转转` (Zhuanzhuan).

Resolve the app's identity:

```bash
app-schema resolve "同程旅行"
```

Inspect an APK:

```bash
app-schema inspect "同程旅行" \
  --artifact tongcheng.apk \
  --jadx /path/to/jadx \
  --output reports/tongcheng.json
```

To inspect an app by name without specifying its package each time, maintain a reviewed source catalog:

```bash
cp app-schema-sources.example.json app-schema-sources.json
app-schema inspect "同程旅行" --output reports/tongcheng.json
```

A source entry can reference a local `artifact_path` or a public `artifact_url`. Remote sources must include a previously verified `sha256`. If the downloaded content changes, inspection stops rather than analyzing an unverified package.

Reuse an existing JADX output directory:

```bash
app-schema inspect "转转" \
  --artifact zhuanzhuan.apk \
  --decoded zhuanzhuan-jadx \
  --output reports/zhuanzhuan.json
```

Inspect an IPA:

```bash
app-schema inspect "Target App" --artifact app.ipa --output reports/app.json
```

Generate a debug URL. By default, the tool rejects parameters without static evidence that the code reads them:

```bash
app-schema probe reports/zhuanzhuan.json \
  --route route:jump/core/searchResult/jump \
  --scheme zhuanzhuan \
  --param 'keyword=乐高 42171' \
  --param searchType=0
```

Record an observed device result:

```bash
app-schema record-test reports/zhuanzhuan.json \
  --platform ios \
  --url 'zhuanzhuan://jump/core/searchResult/jump?...' \
  --outcome correct-page \
  --observed page=search-input \
  --observed keyword=not-consumed \
  --notes 'The search field received focus and the keyboard opened'
```

### Reports

Each inspection produces both JSON and Markdown:

- **Markdown** is a concise capability report for people. It shows a few useful capabilities, with parameter meanings, input formats, use cases, evidence and device results.
- **JSON** is the full audit record for tracing source locations, constructing URLs and appending device observations.
- Add `--audit-index` when you explicitly need the complete route index appended to the Markdown report.

### Codex skill

The repository includes [`skills/app-schema-research`](skills/app-schema-research), which can be installed as a Codex skill. The skill handles app disambiguation, evidence synthesis, parameter interpretation, candidate ranking and A/B probe design. The CLI performs repeatable static scans and records structured evidence.

The LLM interprets findings and proposes the next checks; the scanner provides the facts. Every conclusion must point back to package evidence or device observations. App names and parameter names alone do not establish a verified capability.

## Supported static evidence

- Custom schemes declared in an Android manifest.
- iOS `Info.plist/CFBundleURLTypes/CFBundleURLSchemes`.
- Tongcheng-style `@Router(project, module, visibility)` annotations.
- Zhuanzhuan-style `@Route(tradeLine, pageType, action)` annotations.
- `@RouteParam(name=...)` annotations.
- Parameter reads through `getQueryParameter`, `getStringExtra`, `BridgeData.c`, `Bundle.getString` and similar calls.
- Parameters and constant defaults in RouteBus call chains.
- Complete custom-scheme URLs found in code, JSON, JavaScript and resource files.

## Evidence boundaries

- **Not found in a package does not mean absent.** Routes may be supplied by a server, encrypted or registered at runtime.
- **APK evidence applies to the Android implementation.** It does not establish that an equivalent iOS route exists.
- **An iOS scheme registration does not establish a route or its parameters.** `Info.plist` only proves that the scheme is registered.
- **A capability is production-ready only after device verification.** The URL must open the correct business page and that page must use the target parameters.
- **Ambiguous app identity stops the workflow.** Standard, Pro and related apps are not silently merged.

## Current limitations and next steps

The current version does not search for or download packages from unknown sources. Name-only inspection requires a local APK/IPA entry or a reviewed public download URL with a pinned SHA-256 in the source catalog.

Potential next steps include app-store source plugins, adapters for more routing frameworks, cross-version diffs, interactive device-test checklists and verified capability allowlists for Compy.

## License

[MIT](LICENSE).
