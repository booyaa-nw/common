"""IPv6 のビット計算.

アドレスは128bit整数として扱う。文字列<->整数の変換のみ自前で実装し、ネットワーク/ホスト範囲の
計算はIPv4と同じ考え方(prefixマスク)を128bitに拡張して行う。埋め込みIPv4形式("::ffff:1.2.3.4"等)
は今回のスコープ外(非対応)。
"""

from __future__ import annotations

from dataclasses import dataclass

from common.iptools.calc._bits import full_mask, prefix_mask
from common.iptools.calc.reserved import load_ipv6_reserved, lookup_scope
from common.iptools.result import IPToolsResult, Reason, safe_call

BIT_LENGTH = 128
GROUP_COUNT = 8


def _is_hex_group(text: str) -> bool:
    return 1 <= len(text) <= 4 and all(c in "0123456789abcdefABCDEF" for c in text)


def is_valid_ipv6(ip_str: str) -> bool:
    """"2001:db8::1"のようなIPv6表記として妥当か(埋め込みIPv4形式は非対応)."""
    if ip_str in ("", ":"):
        return False
    if ip_str.count("::") > 1:
        return False
    if ":::" in ip_str:
        return False

    if "::" in ip_str:
        left, right = ip_str.split("::")
        left_groups = left.split(":") if left else []
        right_groups = right.split(":") if right else []
        # "::"は1個以上のゼログループの省略を表すので、明示グループが8個埋まってはいけない
        if len(left_groups) + len(right_groups) >= GROUP_COUNT:
            return False
    else:
        left_groups = ip_str.split(":")
        right_groups = []
        if len(left_groups) != GROUP_COUNT:
            return False

    return all(_is_hex_group(g) for g in left_groups + right_groups)


def ip2long(ip_str: str) -> int:
    """"2001:db8::1" -> 128bit整数. "::"を0埋めして8グループに展開してから連結する."""
    if "::" in ip_str:
        left, right = ip_str.split("::")
        left_groups = left.split(":") if left else []
        right_groups = right.split(":") if right else []
        missing = GROUP_COUNT - (len(left_groups) + len(right_groups))
        groups = left_groups + (["0"] * missing) + right_groups
    else:
        groups = ip_str.split(":")

    value = 0
    for group in groups:
        value = (value << 16) | int(group, 16)
    return value


def long2ip_full(ip_long: int) -> str:
    """128bit整数を省略なしのフル表記(各グループ4桁の16進数)にする."""
    groups = [(ip_long >> shift) & 0xFFFF for shift in range(112, -1, -16)]
    return ":".join(f"{g:04x}" for g in groups)


def long2ip_compressed(ip_long: int) -> str:
    """128bit整数をRFC5952準拠の圧縮表記にする.

    最長の連続0グループを"::"に置換する(タイの場合は最も左側を優先、長さ1は圧縮しない)。
    """
    groups = [(ip_long >> shift) & 0xFFFF for shift in range(112, -1, -16)]

    best_start, best_len = -1, 0
    cur_start, cur_len = -1, 0
    for i, g in enumerate(groups):
        if g == 0:
            if cur_len == 0:
                cur_start = i
            cur_len += 1
            if cur_len > best_len:
                best_start, best_len = cur_start, cur_len
        else:
            cur_len = 0

    if best_len < 2:
        return ":".join(f"{g:x}" for g in groups)

    head = groups[:best_start]
    tail = groups[best_start + best_len :]
    head_str = ":".join(f"{g:x}" for g in head)
    tail_str = ":".join(f"{g:x}" for g in tail)
    return f"{head_str}::{tail_str}"


@dataclass(frozen=True)
class IPv6Info:
    input: str
    address: str  # 圧縮表記
    address_full: str  # フル(展開)表記
    address_int: int
    address_hex: str
    prefix_length: int
    network: str
    network_full: str
    network_int: int
    last_address: str  # サブネット内の最終アドレス(ホスト部が全て1)。IPv6にブロードキャストは無い
    last_address_int: int
    num_addresses: int
    scope: str
    rfc: str
    is_private: bool
    is_global: bool
    is_loopback: bool
    is_link_local: bool
    is_multicast: bool
    is_unspecified: bool


@safe_call
def calc(ip_str: str) -> IPToolsResult[IPv6Info]:
    """"<IPv6>/<プレフィックス長>" を計算する.

    Args:
        ip_str: 例) "2001:db8::1/64"
    """
    text = ip_str.strip()

    if "/" not in text:
        return IPToolsResult.failure(
            Reason.MISSING_PREFIX, f"プレフィックス長の指定がありません: {ip_str!r}"
        )

    addr_part, prefix_part = (p.strip() for p in text.split("/", 1))

    if not is_valid_ipv6(addr_part):
        return IPToolsResult.failure(Reason.INVALID_ADDRESS, f"不正なIPv6アドレスです: {addr_part!r}")

    if not prefix_part.isdigit() or not 0 <= int(prefix_part) <= 128:
        return IPToolsResult.failure(
            Reason.INVALID_PREFIX, f"プレフィックス長は0-128の範囲で指定してください: {prefix_part!r}"
        )
    prefix = int(prefix_part)

    addr_int = ip2long(addr_part)
    mask_int = prefix_mask(prefix, BIT_LENGTH)
    wildcard_int = full_mask(BIT_LENGTH) ^ mask_int

    network_int = addr_int & mask_int
    last_int = addr_int | wildcard_int
    num_addresses = 1 << (BIT_LENGTH - prefix)

    scope, rfc = lookup_scope(addr_int, load_ipv6_reserved())

    info = IPv6Info(
        input=ip_str,
        address=long2ip_compressed(addr_int),
        address_full=long2ip_full(addr_int),
        address_int=addr_int,
        address_hex=f"0x{addr_int:032X}",
        prefix_length=prefix,
        network=long2ip_compressed(network_int),
        network_full=long2ip_full(network_int),
        network_int=network_int,
        last_address=long2ip_compressed(last_int),
        last_address_int=last_int,
        num_addresses=num_addresses,
        scope=scope,
        rfc=rfc,
        is_private=scope == "Unique Local Address (ULA)",
        is_global=scope == "Global",
        is_loopback=scope == "Loopback",
        is_link_local=scope == "Link-local unicast",
        is_multicast=scope == "Multicast",
        is_unspecified=scope == "Unspecified",
    )
    return IPToolsResult.success(info)
