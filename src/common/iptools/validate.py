"""宛先/送信元アドレスとしての妥当性を判定する、複合的なバリデーション.

`iptools.calc`(形式チェック)と`iptools.host`(名前解決・自ホスト判定)を組み合わせて使う、
将来のNW試験ツール(ping等)向けの薄いユーティリティ層。
"""

from __future__ import annotations

from common.iptools.calc.ipv4 import is_valid_ipv4
from common.iptools.host.interfaces import is_my_nic_addr
from common.iptools.host.resolve import is_fqdn, is_resolve
from common.iptools.result import IPToolsResult, Reason, safe_call


@safe_call
def is_valid_dst(dst: str) -> IPToolsResult[None]:
    """宛先として使えるかを判定する.

    IPv4アドレスがそのまま渡された場合は形式チェックのみ行う。FQDNの場合は形式チェックに加え、
    実際に名前解決できるかまで確認する。

    失敗理由(`reason`)は `INVALID_FQDN`(形式不正) と `NOT_RESOLVABLE`(形式は正しいが名前解決不可)
    の2種類に分かれる。
    """
    if is_valid_ipv4(dst):
        return IPToolsResult.success(None)

    fqdn_check = is_fqdn(dst)
    if not fqdn_check.ok:
        return fqdn_check
    if not fqdn_check.value.is_valid:
        return IPToolsResult.failure(
            Reason.INVALID_FQDN, f"FQDNの形式が不正です: {dst!r} ({fqdn_check.value.detail})"
        )

    resolve_check = is_resolve(dst)
    if not resolve_check.ok:
        return resolve_check
    if not resolve_check.value.resolvable:
        return IPToolsResult.failure(Reason.NOT_RESOLVABLE, f"名前解決できません: {dst!r}")

    return IPToolsResult.success(None)


@safe_call
def is_valid_src(src: str) -> IPToolsResult[None]:
    """送信元アドレスとして使えるかを判定する(IPv4形式が妥当で、かつ自ホストのアドレスであること)."""
    if not is_valid_ipv4(src):
        return IPToolsResult.failure(Reason.INVALID_ADDRESS, f"不正なIPv4アドレスです: {src!r}")

    membership = is_my_nic_addr(src)
    if not membership.ok:
        return membership
    if not membership.value.is_mine:
        return IPToolsResult.failure(Reason.NOT_MY_ADDRESS, f"自ホストのIPアドレスではありません: {src!r}")

    return IPToolsResult.success(None)
