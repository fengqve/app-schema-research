import tempfile
import unittest
import json
from pathlib import Path

from appschema.models import AppReport, DynamicTest
from appschema.reporting import build_url, to_markdown
from appschema.scanners import parse_android_manifest, scan_annotation_routes
from appschema.sources import resolve_artifact


class ScannerTests(unittest.TestCase):
    def test_name_only_local_source_registry(self):
        with tempfile.TemporaryDirectory() as holder:
            root = Path(holder)
            artifact = root / "app.apk"
            artifact.write_bytes(b"fixture")
            registry = root / "sources.json"
            registry.write_text(json.dumps({"apps": [{
                "name": "示例 App", "aliases": ["示例"], "artifact_path": "app.apk"
            }]}), "utf-8")
            self.assertEqual(resolve_artifact("示例", registry, root / "cache"), artifact)

    def test_manifest_and_tongcheng_route(self):
        with tempfile.TemporaryDirectory() as holder:
            root = Path(holder)
            resources = root / "resources"
            sources = root / "sources" / "demo"
            resources.mkdir()
            sources.mkdir(parents=True)
            (resources / "AndroidManifest.xml").write_text(
                '<manifest package="com.example" android:versionName="1.2" android:versionCode="3">'
                '<data android:scheme="tctclient" android:host="*"/></manifest>', "utf-8"
            )
            (sources / "Hotel.java").write_text(
                'package demo; @Router(module = "list", project = "hotel", visibility = Visibility.OUTER) '
                'class Hotel { void x(){ data.c("cityId"); data.c(Keys.HOTEL); } } '
                'class Keys { public static final String HOTEL = "hotelName"; }', "utf-8"
            )
            meta, schemes, _ = parse_android_manifest(root)
            self.assertEqual(meta["package"], "com.example")
            self.assertEqual(schemes, ["tctclient"])
            route = scan_annotation_routes(root, schemes)[0]
            self.assertEqual(route.template, "tctclient://hotel/list")
            self.assertTrue({"cityId", "hotelName"}.issubset(route.parameters))

    def test_zhuanzhuan_builder_default(self):
        with tempfile.TemporaryDirectory() as holder:
            root = Path(holder)
            src = root / "sources"
            src.mkdir()
            (src / "Search.java").write_text(
                'package demo; @Route(action = "jump", pageType = "searchResult", tradeLine = "core") '
                'class Search { @RouteParam(name = "keyword") String k; }\n'
                'class Caller { void x(){ bus.setTradeLine("core").setPageType("searchResult")'
                '.setAction("jump").o("keyword", value).i("searchType", 0).d(ctx); } }', "utf-8"
            )
            route = scan_annotation_routes(root, ["zhuanzhuan"])[0]
            self.assertEqual(route.parameters["searchType"].defaults, ["0"])
            self.assertTrue(build_url(route, None, {"keyword": "乐高 42171", "searchType": "0"}).endswith(
                "keyword=%E4%B9%90%E9%AB%98+42171&searchType=0"
            ))

    def test_default_markdown_is_concise_capability_report(self):
        with tempfile.TemporaryDirectory() as holder:
            root = Path(holder)
            src = root / "sources"
            src.mkdir()
            (src / "Search.java").write_text(
                'package demo; @Route(action = "jump", pageType = "searchResult", tradeLine = "core") '
                'class Search { @RouteParam(name = "keyword") String k; }', "utf-8"
            )
            route = scan_annotation_routes(root, ["zhuanzhuan"])[0]
            report = AppReport(query_name="转转", platform="android", routes=[route], schemes=["zhuanzhuan"])
            report.dynamic_tests.append(DynamicTest(
                platform="ios",
                url="zhuanzhuan://jump/core/searchResult/jump?keyword=lego",
                outcome="correct-page",
                observed={"keyword": "not-consumed", "page": "search-input"},
            ))
            markdown = to_markdown(report)
            self.assertIn("搜索结果/列表", markdown)
            self.assertIn("真机未消费", markdown)
            self.assertIn("适用场景", markdown)
            self.assertNotIn("审计路由索引", markdown)


if __name__ == "__main__":
    unittest.main()
