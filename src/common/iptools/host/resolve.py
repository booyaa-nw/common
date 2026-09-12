"""FQDN形式の検証・名前解決."""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass

from common.iptools.result import IPToolsResult, safe_call

_LABEL_LOOSE = re.compile(r"(?!-)[a-z0-9-_]{1,63}(?<!-)$", re.IGNORECASE)
_LABEL_STRICT = re.compile(r"(?!-)[a-z0-9-]{1,63}(?<!-)$", re.IGNORECASE)
_ALL_DIGITS = re.compile(r"^[0-9]+$")


@dataclass(frozen=True)
class FqdnFormatCheck:
    """`is_fqdn`の判定結果。`ok=True`のときだけ意味を持つ."""

    is_valid: bool
    detail: str | None  # 不正な場合の理由。妥当な場合はNone


@safe_call
def is_fqdn(fqdn: str, strict: bool = False) -> IPToolsResult[FqdnFormatCheck]:
    """FQDN/ホスト名の表記が妥当かを判定する(名前解決は行わない).

    strict=Trueの場合、アンダースコアと最上位ラベルの全数字表記を禁則にする。

    ラベル(.間): 63文字以下、ドメイン全体: 253文字以下、先頭/末尾のハイフン・ピリオドは禁則。
    """
    if not fqdn:
        return IPToolsResult.success(FqdnFormatCheck(False, "空文字列です"))
    if fqdn[0] == "." or fqdn[-1] == ".":
        return IPToolsResult.success(FqdnFormatCheck(False, "先頭または末尾がピリオドです"))
    if len(fqdn) > 253:
        return IPToolsResult.success(FqdnFormatCheck(False, "全体が253文字を超えています"))

    labels = fqdn.split(".")
    label_pattern = _LABEL_STRICT if strict else _LABEL_LOOSE

    if strict and _ALL_DIGITS.match(labels[-1]):
        return IPToolsResult.success(FqdnFormatCheck(False, "最上位ラベルが数字のみです"))

    if not all(label_pattern.match(label) for label in labels):
        return IPToolsResult.success(
            FqdnFormatCheck(False, "ラベルに使用できない文字が含まれる、または63文字を超えています")
        )

    return IPToolsResult.success(FqdnFormatCheck(True, None))


@dataclass(frozen=True)
class ResolveCheck:
    """`is_resolve`の判定結果。`ok=True`のときだけ意味を持つ."""

    resolvable: bool
    addresses: tuple[str, ...]  # 解決できた場合のIPアドレス一覧。できない場合は空


@safe_call
def is_resolve(fqdn: str) -> IPToolsResult[ResolveCheck]:
    """名前解決できるかどうかを判定する(実際にDNS/hostsファイルを引く)."""
    try:
        infos = socket.getaddrinfo(fqdn, None)
    except socket.gaierror:
        return IPToolsResult.success(ResolveCheck(resolvable=False, addresses=()))

    addresses = tuple(sorted({info[4][0] for info in infos}))
    return IPToolsResult.success(ResolveCheck(resolvable=True, addresses=addresses))
