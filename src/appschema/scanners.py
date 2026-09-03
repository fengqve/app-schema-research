from __future__ import annotations

import hashlib
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from .models import AppReport, Evidence, Parameter, Route


TEXT_SUFFIXES = {".java", ".kt", ".xml", ".json", ".js", ".bundle", ".txt", ".properties", ".plist"}
SCHEME_LITERAL = re.compile(r"\b([A-Za-z][A-Za-z0-9+.-]*)://([A-Za-z0-9._*-]+)(/[^\s\"'<>)]*)?")
GENERIC_SCHEMES = {"http", "https", "file", "content", "android-app"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def compact_anchor(value: str, limit: int = 240) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def infer_capability(host: str, path: str) -> str:
    value = f"{host}/{path}".lower()
    if any(token in value for token in ("searchresult", "search_result", "search/list", "hotel/list", "hotellist", "newlist")):
        return "search-results"
    if "search" in value:
        return "search-entry"
    if any(token in value for token in ("detail", "details", "item")):
        return "detail"
    if "hotel" in value and "home" in value:
        return "hotel-home"
    if "home" in value:
        return "home"
    if any(token in value for token in ("login", "oauth", "callback", "pay", "share")):
        return "callback-or-account"
    return "unknown"


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            try:
                if path.stat().st_size <= 8 * 1024 * 1024:
                    yield path, path.read_text("utf-8", errors="ignore")
            except OSError:
                continue


def build_string_constant_index(root: Path) -> dict[str, str]:
    candidates: dict[str, set[str]] = {}
    pattern = re.compile(r'(?:public\s+)?(?:static\s+)?final\s+String\s+([A-Za-z_$][\w$]*)\s*=\s*"([A-Za-z0-9_.-]+)"')
    for path, text in iter_text_files(root):
        if path.suffix.lower() not in {".java", ".kt"}:
            continue
        for match in pattern.finditer(text):
            candidates.setdefault(match.group(1), set()).add(match.group(2))
    return {key: next(iter(values)) for key, values in candidates.items() if len(values) == 1}


def extract_params(text: str, path: Path, base: Path, constants: dict[str, str] | None = None) -> dict[str, Parameter]:
    patterns = {
        "RouteParam": re.compile(r'@RouteParam\s*\(\s*name\s*=\s*"([^"]+)"'),
        "query-read": re.compile(r'(?:\.c|getQueryParameter|getStringExtra|optString|getString)\s*\(\s*"([A-Za-z0-9_.-]+)"'),
        "bundle-read": re.compile(r'(?:getString|getInt|getBoolean)\s*\(\s*"([A-Za-z0-9_.-]+)"'),
    }
    result: dict[str, Parameter] = {}
    for accessor, pattern in patterns.items():
        for match in pattern.finditer(text):
            name = match.group(1)
            param = result.setdefault(name, Parameter(name=name))
            if accessor not in param.accessors:
                param.accessors.append(accessor)
            param.evidence.append(Evidence(accessor, str(path.relative_to(base)), line_number(text, match.start()), compact_anchor(match.group(0))))
    constant_pattern = re.compile(
        r'(?:\.c|getQueryParameter|getStringExtra|optString|getString)\s*\(\s*[A-Za-z_$][\w$]*\.([A-Za-z_$][\w$]*)'
    )
    for match in constant_pattern.finditer(text):
        name = (constants or {}).get(match.group(1))
        if not name:
            continue
        param = result.setdefault(name, Parameter(name=name))
        if "resolved-constant" not in param.accessors:
            param.accessors.append("resolved-constant")
        param.evidence.append(Evidence("resolved-constant", str(path.relative_to(base)), line_number(text, match.start()), compact_anchor(match.group(0))))
    return result


def merge_params(target: dict[str, Parameter], incoming: dict[str, Parameter]) -> None:
    for name, item in incoming.items():
        current = target.setdefault(name, Parameter(name=name))
        for accessor in item.accessors:
            if accessor not in current.accessors:
                current.accessors.append(accessor)
        for default in item.defaults:
            if default not in current.defaults:
                current.defaults.append(default)
        current.evidence.extend(item.evidence)


def scan_annotation_routes(root: Path, schemes: list[str]) -> list[Route]:
    routes: dict[str, Route] = {}
    constants = build_string_constant_index(root)
    tongcheng = re.compile(r'@Router\s*\((?P<body>[^)]*)\)', re.S)
    zhuanzhuan = re.compile(r'@Route\s*\((?P<body>[^)]*)\)', re.S)
    for path, text in iter_text_files(root):
        if path.suffix.lower() not in {".java", ".kt"}:
            continue
        class_params = extract_params(text, path, root, constants)
        for match in tongcheng.finditer(text):
            body = match.group("body")
            project = re.search(r'project\s*=\s*"([^"]+)"', body)
            module = re.search(r'module\s*=\s*"([^"]+)"', body)
            if not project or not module:
                continue
            host, route_path = project.group(1), module.group(1)
            rid = f"router:{host}/{route_path}"
            route = routes.setdefault(rid, Route(rid, schemes[0] if len(schemes) == 1 else None, host, route_path))
            route.handler = _class_name(text)
            route.visibility = "OUTER" if "Visibility.OUTER" in body else None
            route.capability = infer_capability(host, route_path)
            route.evidence.append(Evidence("router-annotation", str(path.relative_to(root)), line_number(text, match.start()), compact_anchor(match.group(0))))
            merge_params(route.parameters, class_params)
        for match in zhuanzhuan.finditer(text):
            body = match.group("body")
            trade = re.search(r'tradeLine\s*=\s*"([^"]+)"', body)
            page = re.search(r'pageType\s*=\s*"([^"]+)"', body)
            action = re.search(r'action\s*=\s*"([^"]+)"', body)
            if not trade or not page or not action:
                continue
            host, route_path = "jump", f"{trade.group(1)}/{page.group(1)}/{action.group(1)}"
            rid = f"route:{host}/{route_path}"
            route = routes.setdefault(rid, Route(rid, schemes[0] if len(schemes) == 1 else None, host, route_path))
            route.handler = _class_name(text)
            route.capability = infer_capability(host, route_path)
            route.evidence.append(Evidence("route-annotation", str(path.relative_to(root)), line_number(text, match.start()), compact_anchor(match.group(0))))
            merge_params(route.parameters, class_params)
    attach_route_builder_defaults(root, routes)
    return list(routes.values())


def _class_name(text: str) -> str | None:
    package = re.search(r'^package\s+([\w.]+)', text, re.M)
    cls = re.search(r'\bclass\s+([A-Za-z_$][\w$]*)', text)
    if not cls:
        return None
    return f"{package.group(1)}.{cls.group(1)}" if package else cls.group(1)


def attach_route_builder_defaults(root: Path, routes: dict[str, Route]) -> None:
    chain_pattern = re.compile(
        r'setTradeLine\("(?P<trade>[^"]+)"\).*?setPageType\("(?P<page>[^"]+)"\).*?setAction\("(?P<action>[^"]+)"\)(?P<tail>.{0,900}?)(?:\.d\(|;)',
        re.S,
    )
    param_pattern = re.compile(r'\.(?:o|i)\("([A-Za-z0-9_.-]+)"\s*,\s*([^,)]+)')
    for path, text in iter_text_files(root):
        if path.suffix.lower() not in {".java", ".kt"}:
            continue
        for match in chain_pattern.finditer(text):
            rid = f"route:jump/{match.group('trade')}/{match.group('page')}/{match.group('action')}"
            route = routes.get(rid)
            if not route:
                continue
            for param_match in param_pattern.finditer(match.group("tail")):
                name, raw_default = param_match.groups()
                param = route.parameters.setdefault(name, Parameter(name=name))
                if "route-builder" not in param.accessors:
                    param.accessors.append("route-builder")
                raw_default = raw_default.strip()
                if re.fullmatch(r'"[^"]*"|[-+]?\d+', raw_default) and raw_default not in param.defaults:
                    param.defaults.append(raw_default.strip('"'))
                param.evidence.append(Evidence("route-builder", str(path.relative_to(root)), line_number(text, match.start()), compact_anchor(match.group(0))))


def scan_literal_routes(root: Path, registered_schemes: list[str]) -> list[Route]:
    routes: dict[str, Route] = {}
    allowed = {value.lower() for value in registered_schemes}
    for path, text in iter_text_files(root):
        for match in SCHEME_LITERAL.finditer(text):
            scheme, host, raw_path = match.groups()
            if scheme.lower() in GENERIC_SCHEMES or (allowed and scheme.lower() not in allowed):
                continue
            raw_path = raw_path or ""
            parsed = urlsplit(f"{scheme}://{host}{raw_path}")
            route_path = parsed.path.strip("/")
            rid = f"literal:{scheme.lower()}:{host}/{route_path}"
            route = routes.setdefault(rid, Route(rid, scheme.lower(), host, route_path, source="literal", capability=infer_capability(host, route_path)))
            route.evidence.append(Evidence("literal-url", str(path.relative_to(root)), line_number(text, match.start()), compact_anchor(match.group(0))))
            for key, value in parse_qsl(parsed.query, keep_blank_values=True):
                param = route.parameters.setdefault(key, Parameter(name=key))
                if "literal-query" not in param.accessors:
                    param.accessors.append("literal-query")
                if value and value not in param.defaults:
                    param.defaults.append(value)
    return list(routes.values())


def parse_android_manifest(root: Path) -> tuple[dict[str, str | None], list[str], list[Evidence]]:
    candidates = [root / "resources" / "AndroidManifest.xml", root / "AndroidManifest.xml"]
    manifest = next((item for item in candidates if item.exists()), None)
    if not manifest:
        return {}, [], []
    text = manifest.read_text("utf-8", errors="ignore")
    metadata = {}
    for name, pattern in {
        "package": r'\bpackage="([^"]+)"',
        "version_name": r'android:versionName="([^"]+)"',
        "version_code": r'android:versionCode="([^"]+)"',
    }.items():
        match = re.search(pattern, text)
        metadata[name] = match.group(1) if match else None
    schemes, evidence = [], []
    for match in re.finditer(r'android:scheme="([^"]+)"', text):
        value = match.group(1).lower()
        if value not in GENERIC_SCHEMES and not value.startswith("@") and value not in schemes:
            schemes.append(value)
            evidence.append(Evidence("manifest-scheme", str(manifest.relative_to(root)), line_number(text, match.start()), match.group(0)))
    return metadata, schemes, evidence


def ensure_decoded(apk: Path, decoded: Path | None, jadx: str | None) -> tuple[Path, tempfile.TemporaryDirectory | None]:
    if decoded:
        return decoded, None
    executable = jadx or os.environ.get("JADX_PATH") or shutil.which("jadx")
    if not executable:
        raise RuntimeError("APK 扫描需要 --decoded 指向 JADX 输出目录，或通过 --jadx/JADX_PATH 提供 jadx。")
    holder = tempfile.TemporaryDirectory(prefix="app-schema-jadx-")
    output = Path(holder.name)
    process = subprocess.run([executable, "-d", str(output), str(apk)], text=True, capture_output=True)
    if not (output / "resources" / "AndroidManifest.xml").exists():
        holder.cleanup()
        raise RuntimeError(f"JADX 未生成可读 Manifest：{compact_anchor(process.stderr or process.stdout, 500)}")
    return output, holder


def scan_android(query_name: str, artifact: Path, decoded: Path | None = None, jadx: str | None = None) -> AppReport:
    root, holder = ensure_decoded(artifact, decoded, jadx)
    try:
        metadata, schemes, manifest_evidence = parse_android_manifest(root)
        report = AppReport(
            query_name=query_name,
            platform="android",
            package_id=metadata.get("package"),
            version_name=metadata.get("version_name"),
            version_code=metadata.get("version_code"),
            artifact_path=str(artifact.resolve()),
            artifact_sha256=sha256_file(artifact),
            schemes=schemes,
            evidence=manifest_evidence,
        )
        annotation_routes = scan_annotation_routes(root, schemes)
        literals = scan_literal_routes(root, schemes)
        report.routes = annotation_routes + literals
        if len(schemes) != 1:
            report.warnings.append("多个业务/回调 Scheme 共存，注解路由不能自动归属到某一个 Scheme。")
        report.warnings.append("Android 路由静态存在不等于 iOS 实现；必须单独记录 iOS 真机结果。")
        return report
    finally:
        if holder:
            holder.cleanup()


def _plist_from_app(app_root: Path) -> tuple[dict, Path]:
    info = app_root / "Info.plist"
    if not info.exists():
        raise RuntimeError("未找到 Info.plist")
    return plistlib.loads(info.read_bytes()), info


def scan_ios(query_name: str, artifact: Path) -> AppReport:
    holder = None
    app_root = artifact
    sha = None
    if artifact.suffix.lower() == ".ipa":
        sha = sha256_file(artifact)
        holder = tempfile.TemporaryDirectory(prefix="app-schema-ipa-")
        with zipfile.ZipFile(artifact) as archive:
            archive.extractall(holder.name)
        apps = list((Path(holder.name) / "Payload").glob("*.app"))
        if len(apps) != 1:
            holder.cleanup()
            raise RuntimeError("IPA 中未找到唯一的 Payload/*.app")
        app_root = apps[0]
    try:
        plist, info_path = _plist_from_app(app_root)
        schemes, evidence = [], []
        for url_type in plist.get("CFBundleURLTypes", []) or []:
            for value in url_type.get("CFBundleURLSchemes", []) or []:
                normalized = str(value).lower()
                if normalized not in schemes:
                    schemes.append(normalized)
                    evidence.append(Evidence("plist-scheme", "Info.plist", None, f"CFBundleURLSchemes={value}"))
        report = AppReport(
            query_name=query_name,
            app_name=plist.get("CFBundleDisplayName") or plist.get("CFBundleName"),
            platform="ios",
            package_id=plist.get("CFBundleIdentifier"),
            version_name=plist.get("CFBundleShortVersionString"),
            version_code=str(plist.get("CFBundleVersion", "")) or None,
            artifact_path=str(artifact.resolve()),
            artifact_sha256=sha,
            schemes=schemes,
            evidence=evidence,
        )
        report.routes = scan_literal_routes(app_root, schemes)
        report.warnings.append("iOS Info.plist 只能证明 Scheme 注册；path/query 是否消费仍需代码证据或真机验证。")
        return report
    finally:
        if holder:
            holder.cleanup()


def scan(query_name: str, artifact: Path, decoded: Path | None = None, jadx: str | None = None) -> AppReport:
    if artifact.is_dir() and artifact.suffix.lower() == ".app":
        return scan_ios(query_name, artifact)
    if artifact.suffix.lower() == ".ipa":
        return scan_ios(query_name, artifact)
    if artifact.suffix.lower() == ".apk":
        return scan_android(query_name, artifact, decoded, jadx)
    raise RuntimeError("目前支持 .apk、.ipa 和 .app。")
