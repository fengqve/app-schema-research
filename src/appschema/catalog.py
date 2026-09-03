from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Identity:
    canonical_name: str
    aliases: tuple[str, ...]
    ios_app_store_id: str | None = None
    ios_bundle_id: str | None = None
    android_package: str | None = None


# Identity hints prevent similarly named editions from being merged. They do not
# assert routes or schemes; those must come from an artifact.
IDENTITIES = (
    Identity("同程旅行", ("同程", "同程旅行"), android_package="com.tongcheng.android"),
    Identity("转转", ("转转",), android_package="com.wuba.zhuanzhuan"),
    Identity("飞猪旅行", ("飞猪", "飞猪旅行"), ios_app_store_id="453691481", ios_bundle_id="com.taobao.travel"),
    Identity("去哪儿旅行 Pro", ("去哪儿pro", "去哪儿旅行pro", "去哪儿旅行 pro"), ios_app_store_id="655516874", ios_bundle_id="com.qunar.iPhoneclientpro"),
)


def resolve_identity(name: str) -> Identity | None:
    normalized = "".join(name.lower().split())
    matches = [
        item for item in IDENTITIES
        if normalized in {"".join(alias.lower().split()) for alias in item.aliases}
    ]
    return matches[0] if len(matches) == 1 else None

