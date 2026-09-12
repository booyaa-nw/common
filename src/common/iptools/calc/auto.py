"""IPv4 / IPv6 自動判定."""

from __future__ import annotations

from common.iptools.calc import ipv4, ipv6
from common.iptools.result import IPToolsResult


def calc(ip_str: str) -> IPToolsResult:
    """入力文字列からIPv4/IPv6を自動判定して計算する. ":"を含めばIPv6、含まなければIPv4."""
    addr_part = ip_str.strip().split("/", 1)[0]
    if ":" in addr_part:
        return ipv6.calc(ip_str)
    return ipv4.calc(ip_str)
