from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from .models import AppReport, DynamicTest, Evidence, Parameter, Route


def _evidence(data: dict) -> Evidence:
    return Evidence(**data)


def _parameter(data: dict) -> Parameter:
    data = dict(data)
    data["evidence"] = [_evidence(item) for item in data.get("evidence", [])]
    return Parameter(**data)


def _route(data: dict) -> Route:
    data = dict(data)
    data["evidence"] = [_evidence(item) for item in data.get("evidence", [])]
    data["parameters"] = {key: _parameter(value) for key, value in data.get("parameters", {}).items()}
    return Route(**data)


def load_report(path: Path) -> AppReport:
    data = json.loads(path.read_text("utf-8"))
    data["evidence"] = [_evidence(item) for item in data.get("evidence", [])]
    data["routes"] = [_route(item) for item in data.get("routes", [])]
    data["dynamic_tests"] = [DynamicTest(**item) for item in data.get("dynamic_tests", [])]
    return AppReport(**data)


def save_report(report: AppReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), "utf-8")


def build_url(route: Route, scheme: str | None, params: dict[str, str]) -> str:
    selected_scheme = scheme or route.scheme
    if not selected_scheme:
        raise ValueError("该路由未能静态归属 Scheme，请用 --scheme 明确指定。")
    base = f"{selected_scheme}://{route.host}"
    if route.path:
        base += f"/{route.path}"
    return base + ("?" + urlencode(params) if params else "")


PARAMETER_MEANINGS = {
    "keyword": ("搜索关键词", "普通文本，需 URL 编码"),
    "hotelName": ("酒店名或酒店关键词", "普通文本，是否作为搜索词必须真机确认"),
    "tagname": ("筛选标签或目的地关键词", "普通文本，具体实体类型需 A/B"),
    "tagName": ("筛选标签名称", "普通文本，具体实体类型需 A/B"),
    "poiName": ("兴趣点名称", "通常需与对应 POI ID/类型配套"),
    "cityId": ("目的地城市 ID", "字符串或数字；不是行政区划码时需使用 App 内部 ID"),
    "cityName": ("目的地城市名称", "普通文本，通常与 cityId 配套"),
    "checkInDate": ("入住日期", "YYYY-MM-DD"),
    "checkOutDate": ("离店日期", "YYYY-MM-DD"),
    "globalCheckInDate": ("国际酒店入住日期", "YYYY-MM-DD"),
    "globalCheckOutDate": ("国际酒店离店日期", "YYYY-MM-DD"),
    "searchType": ("搜索类型开关", "整数枚举；各取值语义需结合调用点或 A/B"),
    "cateId": ("商品分类 ID", "App 内部分类 ID"),
    "cityId": ("城市 ID", "App 内部 ID；不要默认当作行政区划码"),
    "from": ("来源场景", "内部归因值，通常不是业务必填"),
    "hotelId": ("酒店实体 ID", "必须使用 App/服务端认可的内部 ID"),
    "sceneryId": ("景点实体 ID", "必须使用 App/服务端认可的内部 ID"),
    "adultNum": ("成人数", "整数"),
    "childrenAges": ("儿童年龄", "数组或分隔字符串，格式需调用点确认"),
}

PARAMETER_PRIORITY = {
    "keyword": 100,
    "hotelName": 99,
    "tagname": 96,
    "tagName": 95,
    "poiName": 94,
    "cityId": 93,
    "cityName": 92,
    "checkInDate": 91,
    "checkOutDate": 90,
    "globalCheckInDate": 89,
    "globalCheckOutDate": 88,
    "hotelId": 87,
    "searchType": 80,
    "cateId": 75,
    "adultNum": 74,
    "childrenAges": 73,
}

CAPABILITY_LABELS = {
    "search-results": ("搜索结果/列表", "从第三方 App 带条件进入结果页"),
    "search-entry": ("搜索入口", "打开目标 App 的搜索输入或目的地选择页面"),
    "hotel-home": ("酒店频道首页", "进入酒店业务模块，再由用户手动搜索"),
    "detail": ("实体详情", "已知内部实体 ID 时直达详情"),
    "home": ("业务首页", "进入指定业务频道或首页"),
}


def _test_route_key(test: DynamicTest) -> tuple[str, str, str]:
    parsed = urlsplit(test.url)
    return parsed.scheme, parsed.netloc, parsed.path.strip("/")


def _route_tests(report: AppReport, route: Route) -> list[DynamicTest]:
    matches = []
    for test in report.dynamic_tests:
        _, host, path = _test_route_key(test)
        if host == route.host and path == route.path.strip("/"):
            matches.append(test)
    return matches


def _display_scheme(report: AppReport, route: Route, tests: list[DynamicTest]) -> str | None:
    if route.scheme:
        return route.scheme
    if tests:
        return _test_route_key(tests[-1])[0]
    # A literal URL with the same host/path can bind an annotated route to a Scheme.
    for candidate in report.routes:
        if candidate.scheme and candidate.host == route.host and candidate.path == route.path:
            return candidate.scheme
    return None


def _route_score(report: AppReport, route: Route) -> int:
    score = {
        "search-results": 60,
        "search-entry": 50,
        "hotel-home": 45,
        "detail": 25,
        "home": 15,
    }.get(route.capability, 0)
    if _route_tests(report, route):
        score += 100
    if route.visibility == "OUTER":
        score += 30
    if route.source == "literal":
        score += 20
    useful = sum(1 for key in route.parameters if key in PARAMETER_PRIORITY)
    return score + min(useful * 3, 24)


def _select_capabilities(report: AppReport, limit: int = 8) -> list[Route]:
    candidates = [
        route for route in report.routes
        if route.capability in CAPABILITY_LABELS
        and (_route_score(report, route) >= 45 or _route_tests(report, route))
    ]
    # Prefer annotation handlers over duplicate literal strings, but retain the latter as evidence.
    grouped: dict[tuple[str, str], Route] = {}
    for route in sorted(candidates, key=lambda item: _route_score(report, item), reverse=True):
        key = (route.host.lower(), route.path.lower())
        previous = grouped.get(key)
        if previous is None or (previous.source == "literal" and route.handler):
            grouped[key] = route
    externally_addressable = []
    for route in grouped.values():
        tests = _route_tests(report, route)
        if not _display_scheme(report, route, tests):
            continue
        useful = any(key in PARAMETER_PRIORITY for key in route.parameters)
        if route.capability == "detail" and not useful and not tests:
            continue
        externally_addressable.append(route)
    return sorted(externally_addressable, key=lambda item: _route_score(report, item), reverse=True)[:limit]


def _parameter_status(name: str, tests: list[DynamicTest]) -> str:
    aliases = {
        "cityId": {"city"},
        "cityName": {"city"},
        "checkInDate": {"dates"},
        "checkOutDate": {"dates"},
        "globalCheckInDate": {"dates"},
        "globalCheckOutDate": {"dates"},
    }
    states = []
    for test in tests:
        for key, value in test.observed.items():
            if key.lower() == name.lower() or key in aliases.get(name, set()):
                states.append(value)
    if any(value == "consumed" for value in states):
        return "真机已消费"
    if any(value == "not-consumed" for value in states):
        return "真机未消费"
    return "仅静态候选"


def _route_conclusion(route: Route, tests: list[DynamicTest]) -> str:
    if not tests:
        return "包内静态确认，尚未验证外部调用"
    last = tests[-1]
    failed = [key for key, value in last.observed.items() if value == "not-consumed"]
    consumed = [key for key, value in last.observed.items() if value == "consumed"]
    if last.outcome in {"wrong-page", "error", "no-handler"}:
        return f"真机失败：{last.outcome}"
    if failed:
        prefix = f"已进入目标页面；{', '.join(consumed)} 生效；" if consumed else "已打开页面；"
        return prefix + f"{', '.join(failed)} 未生效，仅适合继续 Debug"
    if last.outcome == "results" and consumed:
        return "真机已进入结果页并消费目标参数，可作为生产候选"
    return "真机已打开对应页面，但关键业务参数仍需确认"


def _example_url(route: Route, scheme: str | None, tests: list[DynamicTest]) -> str:
    if tests:
        return tests[-1].url
    if not scheme:
        return "缺少 Scheme 归属，暂不能生成外部 URL"
    return build_url(route, scheme, {})


def _business_schemes(schemes: list[str]) -> list[str]:
    callback_markers = ("wx", "tencent", "qwallet", "alipay", "tingyun")
    return [
        item for item in schemes
        if not item.lower().startswith(callback_markers)
        and not item.lower().endswith("push")
    ]


def _application(route: Route) -> str:
    domain = route.host.lower()
    if "hotel" in domain and route.capability == "search-results":
        return "从行程、日历或比价工具带入目的地和日期，减少在酒店 App 内重复填写。"
    if route.capability == "search-results":
        return "从识别、收藏或比价场景把用户送到目标 App 的搜索结果。"
    if route.capability == "search-entry":
        return "作为无法可靠传入关键词时的降级入口，让用户在目标 App 内继续输入。"
    if route.capability == "hotel-home":
        return "作为酒店直搜失败时的业务频道降级入口。"
    if route.capability == "detail":
        return "在已知目标 App 内部实体 ID 时，从外部页面直达详情。"
    return "从第三方 App 进入目标业务模块。"


def to_markdown(report: AppReport, include_audit_index: bool = False) -> str:
    selected = _select_capabilities(report, limit=3)
    used_schemes = []
    for route in selected:
        scheme = _display_scheme(report, route, _route_tests(report, route))
        if scheme and scheme not in used_schemes:
            used_schemes.append(scheme)
    lines = [f"# App Schema 报告：{report.query_name}", ""]
    lines += [
        f"- 平台：`{report.platform or '未知'}`",
        f"- 包标识：`{report.package_id or '未知'}`",
        f"- 版本：`{report.version_name or '未知'}`（build `{report.version_code or '未知'}`）",
        f"- SHA-256：`{report.artifact_sha256 or '目录输入，未计算'}`",
        f"- 可关联到下列能力的 Scheme：{', '.join(f'`{item}`' for item in used_schemes) or '未确认'}",
        f"- 其余注册 Scheme：{len(report.schemes) - len(used_schemes)} 个，仅保留在 JSON 审计底稿",
        "",
        "## 结论",
        "",
    ]
    if not selected:
        lines.append("没有找到证据足够的外部业务能力候选。完整静态结果保存在 JSON 审计文件中。")
    else:
        lines.append(f"找到 {len(selected)} 项值得继续验证的业务能力；以下已去除回调 Scheme、内部测试页和重复路由。")
    for index, route in enumerate(selected, 1):
        tests = _route_tests(report, route)
        scheme = _display_scheme(report, route, tests)
        label, scenario = CAPABILITY_LABELS[route.capability]
        template = f"{scheme}://{route.host}/{route.path}" if scheme else f"<未绑定Scheme>://{route.host}/{route.path}"
        lines += [
            "",
            f"## {index}. {label}：`{template}`",
            "",
            f"- **作用**：{scenario}。",
            f"- **当前判断**：{_route_conclusion(route, tests)}。",
            f"- **处理模块**：`{route.handler or '仅发现包内 URL 字符串'}`。",
            f"- **适用场景**：{_application(route)}",
            "",
        ]
        names = sorted(route.parameters, key=lambda key: (-PARAMETER_PRIORITY.get(key, 0), key.lower()))
        meaningful = [name for name in names if name in PARAMETER_PRIORITY][:8]
        if meaningful:
            lines += ["### 有用参数", "", "| 参数 | 含义 | 入参方式 | 证据状态 |", "|---|---|---|---|"]
            for name in meaningful:
                meaning, usage = PARAMETER_MEANINGS.get(name, ("业务参数", "格式需结合调用点确认"))
                lines.append(f"| `{name}` | {meaning} | {usage} | {_parameter_status(name, tests)} |")
        else:
            lines += ["### 有用参数", "", "尚未找到值得第三方调用的业务参数。"]
        shortest = f"{scheme}://{route.host}/{route.path}" if scheme else "无法生成"
        lines += ["", "### 调用示例", "", f"最短探针：`{shortest}`"]
        example = _example_url(route, scheme, tests)
        if example != shortest:
            lines += ["", "已测试或完整参数示例：", "", f"```text\n{example}\n```"]
        evidence = list(route.evidence)
        for candidate in report.routes:
            if candidate is not route and candidate.host == route.host and candidate.path == route.path:
                evidence.extend(candidate.evidence)
        if evidence:
            lines += ["", "### 最小复核证据", ""]
            for item in evidence[:2]:
                suffix = f":{item.line}" if item.line else ""
                lines.append(f"- `{item.path}{suffix}`（{item.kind}）")
        if tests:
            lines += ["", "### 真机结果", ""]
            for test in tests[-2:]:
                observed = "，".join(f"{k}={v}" for k, v in test.observed.items()) or "无结构化观察"
                lines.append(f"- {test.platform}：{test.outcome}；{observed}。{test.notes}")
    lines += [
        "",
        "## 未展示内容",
        "",
        f"完整扫描得到 {len(report.routes)} 条路由。默认报告不展示回调、账户、订单、内部测试页及低价值重复项；需要追溯时查看同名 JSON。",
    ]
    if include_audit_index:
        lines += ["", "## 审计路由索引", "", "| route_id | 模板 | 能力 | 参数数 |", "|---|---|---|---:|"]
        for route in report.routes:
            lines.append(f"| `{route.route_id}` | `{route.template or '未绑定 Scheme'}` | {route.capability} | {len(route.parameters)} |")
    if report.warnings:
        lines += ["", "## 边界", ""] + [f"- {item}" for item in report.warnings]
    return "\n".join(lines) + "\n"
