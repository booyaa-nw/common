"""自ホストのNIC/IPアドレス情報の取得 (psutilを利用)."""

from __future__ import annotations

import socket
from dataclasses import dataclass

import psutil

from common.iptools.calc.ipv4 import is_valid_ipv4
from common.iptools.calc.ipv6 import is_valid_ipv6
from common.iptools.result import IPToolsResult, Reason, safe_call


@dataclass(frozen=True)
class NicAddress:
    interface: str
    address: str


@dataclass(frozen=True)
class MyNics:
    ipv4: tuple[NicAddress, ...]
    ipv6: tuple[NicAddress, ...]


@safe_call
def get_my_nics() -> IPToolsResult[MyNics]:
    """自ホストの全NICのIPv4/IPv6アドレス一覧を取得する."""
    ipv4_list: list[NicAddress] = []
    ipv6_list: list[NicAddress] = []

    for interface, snics in psutil.net_if_addrs().items():
        for snic in snics:
            if snic.family == socket.AF_INET:
                ipv4_list.append(NicAddress(interface, snic.address))
            elif snic.family == socket.AF_INET6:
                # link-local等でscope id("%eth0"等)が付くことがあるため取り除く
                address = snic.address.split("%")[0]
                ipv6_list.append(NicAddress(interface, address))

    return IPToolsResult.success(MyNics(ipv4=tuple(ipv4_list), ipv6=tuple(ipv6_list)))


@dataclass(frozen=True)
class MembershipCheck:
    """`is_my_nic_addr`の判定結果。`ok=True`のときだけ意味を持つ."""

    is_mine: bool
    matched_interface: str | None


@safe_call
def is_my_nic_addr(address: str) -> IPToolsResult[MembershipCheck]:
    """指定したIPアドレスが自ホストのいずれかのNICに割り当てられているかを判定する."""
    if not (is_valid_ipv4(address) or is_valid_ipv6(address)):
        return IPToolsResult.failure(Reason.INVALID_ADDRESS, f"不正なIPアドレスです: {address!r}")

    nics_result = get_my_nics()
    if not nics_result.ok:
        return nics_result

    for nic in (*nics_result.value.ipv4, *nics_result.value.ipv6):
        if nic.address == address:
            return IPToolsResult.success(MembershipCheck(is_mine=True, matched_interface=nic.interface))

    return IPToolsResult.success(MembershipCheck(is_mine=False, matched_interface=None))
