"""Special-Purpose Address Registry (予約済みアドレス) の参照.

`data/ipv4_reserved.csv` / `data/ipv6_reserved.csv` (address,scope,rfc の3列CSV) を読み込み、
指定アドレス(整数)が該当する予約範囲を最長一致で判定する。`ipaddress` は使わず、CIDR文字列を
自前でパースしてビットマスクで判定する。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Iterable

from common.iptools.calc._bits import prefix_mask


@dataclass(frozen=True)
class ReservedEntry:
    network_int: int
    prefix_length: int
    bit_length: int
    scope: str
    rfc: str

    def contains(self, addr_int: int) -> bool:
        mask = prefix_mask(self.prefix_length, self.bit_length)
        return (addr_int & mask) == self.network_int


def _parse_cidr_v4(cidr: str) -> tuple[int, int]:
    # 循環import回避のため関数内でimportする(reservedはipv4/ipv6から使われる側のため)
    from common.iptools.calc.ipv4 import ip2long

    addr, prefix = cidr.split("/")
    return ip2long(addr), int(prefix)


def _parse_cidr_v6(cidr: str) -> tuple[int, int]:
    from common.iptools.calc.ipv6 import ip2long

    addr, prefix = cidr.split("/")
    return ip2long(addr), int(prefix)


def _load_csv(resource_name: str, bit_length: int) -> list[ReservedEntry]:
    parse = _parse_cidr_v4 if bit_length == 32 else _parse_cidr_v6
    data_text = (
        resources.files("common.iptools").joinpath("data", resource_name).read_text(encoding="utf-8")
    )
    entries: list[ReservedEntry] = []
    reader = csv.DictReader(data_text.splitlines())
    for row in reader:
        network_int, prefix = parse(row["address"])
        entries.append(
            ReservedEntry(
                network_int=network_int,
                prefix_length=prefix,
                bit_length=bit_length,
                scope=row["scope"],
                rfc=row["rfc"],
            )
        )
    # 最長一致(prefixが大きいもの)を優先して判定できるようソートしておく
    entries.sort(key=lambda e: e.prefix_length, reverse=True)
    return entries


@lru_cache(maxsize=None)
def load_ipv4_reserved() -> tuple[ReservedEntry, ...]:
    return tuple(_load_csv("ipv4_reserved.csv", 32))


@lru_cache(maxsize=None)
def load_ipv6_reserved() -> tuple[ReservedEntry, ...]:
    return tuple(_load_csv("ipv6_reserved.csv", 128))


def lookup_scope(addr_int: int, entries: Iterable[ReservedEntry]) -> tuple[str, str]:
    """addr_int が該当する予約範囲を最長一致で探す。見つからなければ ("Global", "") を返す。"""
    for entry in entries:
        if entry.contains(addr_int):
            return entry.scope, entry.rfc
    return "Global", ""
