from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def _normalized(value: str) -> str:
    return "".join(value.lower().split())


def resolve_artifact(app_name: str, registry_path: Path, cache_dir: Path) -> Path:
    if not registry_path.exists():
        raise RuntimeError(
            "未提供 --artifact，且来源目录不存在。请传入安装包，或按 README 配置经过审核的来源目录。"
        )
    data = json.loads(registry_path.read_text("utf-8"))
    query = _normalized(app_name)
    matches = []
    for item in data.get("apps", []):
        names = [item.get("name", ""), *item.get("aliases", [])]
        if query in {_normalized(name) for name in names}:
            matches.append(item)
    if len(matches) != 1:
        raise RuntimeError(f"来源目录对“{app_name}”命中 {len(matches)} 项，必须先消歧。")
    item = matches[0]
    if item.get("artifact_path"):
        path = Path(item["artifact_path"])
        if not path.is_absolute():
            path = registry_path.parent / path
        if not path.exists():
            raise RuntimeError(f"来源目录中的安装包不存在：{path}")
        return path
    url = item.get("artifact_url")
    expected_sha = item.get("sha256")
    if not url or not expected_sha:
        raise RuntimeError("远程来源必须同时声明 artifact_url 和 sha256，避免静默换包。")
    suffix = Path(urlparse(url).path).suffix or item.get("suffix", ".apk")
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"{expected_sha}{suffix}"
    if not destination.exists():
        with urllib.request.urlopen(url, timeout=60) as response, destination.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    digest = hashlib.sha256()
    with destination.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual.lower() != expected_sha.lower():
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"来源包 SHA-256 不匹配：期望 {expected_sha}，实际 {actual}")
    return destination
