from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .catalog import resolve_identity
from .models import DynamicTest
from .reporting import build_url, load_report, save_report, to_markdown
from .scanners import scan
from .sources import resolve_artifact


def parse_pairs(values: list[str]) -> dict[str, str]:
    result = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"参数必须是 key=value：{value}")
        key, item = value.split("=", 1)
        result[key] = item
    return result


def inspect_command(args: argparse.Namespace) -> int:
    artifact = Path(args.artifact) if args.artifact else resolve_artifact(
        args.app_name, Path(args.registry), Path(args.cache_dir)
    )
    decoded = Path(args.decoded) if args.decoded else None
    report = scan(args.app_name, artifact, decoded, args.jadx)
    identity = resolve_identity(args.app_name)
    if identity:
        report.app_name = identity.canonical_name
        expected = identity.android_package if report.platform == "android" else identity.ios_bundle_id
        if expected and report.package_id != expected:
            raise RuntimeError(f"身份不匹配：输入为 {identity.canonical_name}，包内标识为 {report.package_id}，预期 {expected}")
    output = Path(args.output)
    save_report(report, output)
    markdown = output.with_suffix(".md")
    markdown.write_text(to_markdown(report, include_audit_index=args.audit_index), "utf-8")
    print(json.dumps({"report": str(output), "markdown": str(markdown), "routes": len(report.routes), "schemes": report.schemes}, ensure_ascii=False))
    return 0


def probe_command(args: argparse.Namespace) -> int:
    report = load_report(Path(args.report))
    route = next((item for item in report.routes if item.route_id == args.route), None)
    if not route:
        raise ValueError(f"没有该 route_id：{args.route}")
    params = parse_pairs(args.param)
    unknown = sorted(set(params) - set(route.parameters))
    if unknown and not args.allow_unverified:
        raise ValueError(f"这些参数没有静态消费证据：{', '.join(unknown)}；如仅用于 A/B，请加 --allow-unverified")
    print(build_url(route, args.scheme, params))
    return 0


def record_command(args: argparse.Namespace) -> int:
    path = Path(args.report)
    report = load_report(path)
    report.dynamic_tests.append(DynamicTest(
        platform=args.platform,
        url=args.url,
        outcome=args.outcome,
        observed=parse_pairs(args.observed),
        notes=args.notes or "",
        tested_at=datetime.now(timezone.utc).isoformat(),
    ))
    save_report(report, path)
    path.with_suffix(".md").write_text(to_markdown(report), "utf-8")
    print(f"已记录：{args.platform} / {args.outcome}")
    return 0


def resolve_command(args: argparse.Namespace) -> int:
    identity = resolve_identity(args.app_name)
    if not identity:
        print("未唯一命中本地身份目录；请提供 App Store ID、Bundle ID 或 Android 包名。", file=sys.stderr)
        return 2
    print(json.dumps(identity.__dict__, ensure_ascii=False, indent=2))
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app-schema", description="证据优先的移动 App 自定义 URL Scheme 调查工具")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve", help="消歧并确认 App 身份")
    resolve.add_argument("app_name")
    resolve.set_defaults(func=resolve_command)

    inspect = sub.add_parser("inspect", help="扫描 APK、IPA 或 app")
    inspect.add_argument("app_name")
    inspect.add_argument("--artifact", help="本地 APK、IPA 或 .app；省略时从经过审核的来源目录解析")
    inspect.add_argument("--registry", default="app-schema-sources.json", help="按 App 名解析安装包的来源目录")
    inspect.add_argument("--cache-dir", default=".app-schema-cache", help="校验通过的远程安装包缓存目录")
    inspect.add_argument("--decoded", help="已有 JADX 输出目录，可避免重复反编译")
    inspect.add_argument("--jadx", help="jadx 可执行文件路径")
    inspect.add_argument("--output", default="app-schema-report.json")
    inspect.add_argument("--audit-index", action="store_true", help="在 Markdown 末尾附加全量路由索引；默认只输出能力卡片")
    inspect.set_defaults(func=inspect_command)

    probe = sub.add_parser("probe", help="基于已确认路由生成 Debug URL")
    probe.add_argument("report")
    probe.add_argument("--route", required=True)
    probe.add_argument("--scheme")
    probe.add_argument("--param", action="append", default=[])
    probe.add_argument("--allow-unverified", action="store_true")
    probe.set_defaults(func=probe_command)

    record = sub.add_parser("record-test", help="记录真机验证结果")
    record.add_argument("report")
    record.add_argument("--platform", choices=("ios", "android"), required=True)
    record.add_argument("--url", required=True)
    record.add_argument("--outcome", choices=("no-handler", "opened-app", "correct-page", "results", "wrong-page", "error"), required=True)
    record.add_argument("--observed", action="append", default=[])
    record.add_argument("--notes")
    record.set_defaults(func=record_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, ValueError, OSError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
