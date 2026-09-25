"""IPv4 のビット計算.

標準ライブラリ `ipaddress` は使わず、bit演算で計算する。ネットワークエンジニアがコードを
読んだときに、サブネット計算の仕組みがそのまま理解できることを重視している。
"""

from __future__ import annotations

from dataclasses import dataclass

from common.iptools.calc._bits import full_mask, prefix_mask
from common.iptools.calc.reserved import load_ipv4_reserved, lookup_scope
from common.iptools.result import IPToolsResult, Reason, safe_call

BIT_LENGTH = 32


def _is_valid_octet(text: str) -> bool:
    """"192"のような1オクテット分の文字列が0-255の範囲か."""
    return text.isdigit() and len(text) <= 3 and 0 <= int(text) <= 255


def is_valid_ipv4(ip_str: str) -> bool:
    """"192.168.1.1"のようなドット区切り4オクテット表記として妥当か."""
    parts = ip_str.split(".")
    return len(parts) == 4 and all(_is_valid_octet(p) for p in parts)


def ip2long(ip_str: str) -> int:
    """"192.168.1.1" -> 3232235777. 各オクテットを8bitずつ左シフトして連結する."""
    value = 0
    for octet in ip_str.split("."):
        value = (value << 8) | int(octet)
    return value


def long2ip(ip_long: int) -> str:
    """3232235777 -> "192.168.1.1". 8bitずつ、上位バイトから順に取り出す."""
    return ".".join(str((ip_long >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def is_valid_dotted_mask(mask_str: str) -> bool:
    """"255.255.255.0"のような、1が連続したあとに0が続くマスク表記として妥当か."""
    if not is_valid_ipv4(mask_str):
        return False
    binary = format(ip2long(mask_str), "032b")
    # "1"の後に"0"が来て、その後にまた"1"が来る(=1が連続していない)ものは不正なマスク
    return "01" not in binary


def dotted_mask_to_cidr(mask_str: str) -> int:
    """"255.255.255.0" -> 24. 立っているビットの数を数える."""
    return format(ip2long(mask_str), "032b").count("1")


def cidr_to_dotted_mask(cidr: int) -> str:
    """24 -> "255.255.255.0"."""
    return long2ip(prefix_mask(cidr, BIT_LENGTH))


def _classify(first_octet: int) -> str:
    """クラスフル(歴史的)なIPアドレスクラスを返す."""
    if first_octet <= 126:
        return "A"
    if first_octet <= 191:
        return "B"
    if first_octet <= 223:
        return "C"
    if first_octet <= 239:
        return "D"
    return "E"


@dataclass(frozen=True)
class IPv4Info:
    input: str
    address: str
    prefix_length: int
    netmask: str
    wildcard_mask: str
    network: str
    broadcast: str
    host_min: str
    host_max: str
    num_hosts: int
    num_addresses: int
    address_int: int
    network_int: int
    broadcast_int: int
    address_hex: str
    network_hex: str
    broadcast_hex: str
    ip_class: str
    scope: str
    rfc: str
    is_private: bool
    is_global: bool
    is_loopback: bool
    is_link_local: bool
    is_multicast: bool
    is_unspecified: bool


@safe_call
def calc(ip_str: str) -> IPToolsResult[IPv4Info]:
    """"<IPv4>/<CIDR>" または "<IPv4>/<NetMask>" を計算する.

    Args:
        ip_str: 例) "192.168.1.1/24", "192.168.1.1/255.255.255.0"
    """
    text = ip_str.strip()

    if "/" not in text:
        return IPToolsResult.failure(
            Reason.MISSING_PREFIX,
            f"CIDRまたはネットマスクの指定がありません: {ip_str!r}",
        )

    addr_part, mask_part = (p.strip() for p in text.split("/", 1))

    if not is_valid_ipv4(addr_part):
        return IPToolsResult.failure(Reason.INVALID_ADDRESS, f"不正なIPv4アドレスです: {addr_part!r}")

    if mask_part.isdigit():
        prefix = int(mask_part)
        if not 0 <= prefix <= 32:
            return IPToolsResult.failure(
                Reason.INVALID_PREFIX, f"CIDRは0-32の範囲で指定してください: {mask_part!r}"
            )
    elif is_valid_dotted_mask(mask_part):
        prefix = dotted_mask_to_cidr(mask_part)
    else:
        return IPToolsResult.failure(Reason.INVALID_PREFIX, f"不正なCIDR/ネットマスクです: {mask_part!r}")

    addr_int = ip2long(addr_part)
    mask_int = prefix_mask(prefix, BIT_LENGTH)
    wildcard_int = full_mask(BIT_LENGTH) ^ mask_int

    network_int = addr_int & mask_int
    broadcast_int = addr_int | wildcard_int
    num_addresses = 1 << (BIT_LENGTH - prefix)

    # RFC3021: /31はポイントツーポイントリンク用に両アドレスとも使用可能、/32はホストルート
    if prefix >= 31:
        host_min_int = network_int
        host_max_int = broadcast_int
        num_hosts = num_addresses
    else:
        host_min_int = network_int + 1
        host_max_int = broadcast_int - 1
        num_hosts = num_addresses - 2

    scope, rfc = lookup_scope(addr_int, load_ipv4_reserved())

    info = IPv4Info(
        input=ip_str,
        address=addr_part,
        prefix_length=prefix,
        netmask=long2ip(mask_int),
        wildcard_mask=long2ip(wildcard_int),
        network=long2ip(network_int),
        broadcast=long2ip(broadcast_int),
        host_min=long2ip(host_min_int),
        host_max=long2ip(host_max_int),
        num_hosts=num_hosts,
        num_addresses=num_addresses,
        address_int=addr_int,
        network_int=network_int,
        broadcast_int=broadcast_int,
        address_hex=f"0x{addr_int:08X}",
        network_hex=f"0x{network_int:08X}",
        broadcast_hex=f"0x{broadcast_int:08X}",
        ip_class=_classify(addr_int >> 24),
        scope=scope,
        rfc=rfc,
        is_private=scope == "Private",
        is_global=scope == "Global",
        is_loopback=scope == "Loopback",
        is_link_local=scope == "Link Local",
        is_multicast=scope == "Multicast",
        is_unspecified=addr_part == "0.0.0.0",
    )
    return IPToolsResult.success(info)
