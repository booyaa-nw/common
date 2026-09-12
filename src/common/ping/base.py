"""OS非依存の ping 結果モデルと ICMP/IP_STATUS 対応表.

`tools/mping` で自己完結モジュールとして実装・pytest済みの上で本モジュール
(`common.ping.base`)へ移植したもの(移植元: `mping/ping/base.py`)。
"""

from __future__ import annotations

from dataclasses import dataclass

ICMP_TYPE_ECHO_REPLY = 0
ICMP_TYPE_TTL_EXCEEDED = 11

# 実ICMP応答が全く無い場合(タイムアウト等)に使う、アプリ内部の疑似type/code。
# ログ(`type`/`code`列)を常に数値で埋めるための呼び出し側アプリ固有の取り決めであり、
# RFC792のICMP typeとは無関係(実在するICMP typeの値と衝突しない98/99を使う)。
TYPE_NO_REPLY = 98  # 純粋なタイムアウト(応答自体を受信できなかった)
TYPE_UNKNOWN_ERROR = 99  # 送信自体の失敗(経路なし等)、その他分類不能なエラー
CODE_NONE = 0


@dataclass(frozen=True)
class PingResult:
    """1回の ping 送信結果 (OS非依存)."""

    ok: bool
    rtt: float | None  # 秒。タイムアウト時は None
    icmp_type: int | None
    icmp_code: int | None
    reply_from: str | None = None  # 実際に応答したホストのアドレス(TTL超過時は中継ルータ)
    message: str | None = None


# Windows IcmpSendEcho/IcmpSendEcho2Ex が返す IP_STATUS 値から
# (ICMP type, ICMP code) への変換表。
# IP_STATUS は RFC792 の ICMP type/code とは別の Windows 独自コードのため、
# `iphlpapi.dll` を使う場合でも直接 ICMP type/code が得られるわけではなく、
# この変換表を介した近似マッピングが必要になる。
IP_STATUS_SUCCESS = 0
IP_STATUS_BUF_TOO_SMALL = 11001
IP_STATUS_DEST_NET_UNREACHABLE = 11002
IP_STATUS_DEST_HOST_UNREACHABLE = 11003
IP_STATUS_DEST_PROT_UNREACHABLE = 11004
IP_STATUS_DEST_PORT_UNREACHABLE = 11005
IP_STATUS_NO_RESOURCES = 11006
IP_STATUS_BAD_OPTION = 11007
IP_STATUS_HW_ERROR = 11008
IP_STATUS_PACKET_TOO_BIG = 11009
IP_STATUS_REQ_TIMED_OUT = 11010
IP_STATUS_BAD_REQ = 11011
IP_STATUS_BAD_ROUTE = 11012
IP_STATUS_TTL_EXPIRED_TRANSIT = 11013
IP_STATUS_TTL_EXPIRED_REASSEM = 11014
IP_STATUS_PARAM_PROBLEM = 11015
IP_STATUS_SOURCE_QUENCH = 11016
IP_STATUS_OPTION_TOO_BIG = 11017
IP_STATUS_BAD_DESTINATION = 11018

# status -> (icmp_type, icmp_code)
IP_STATUS_TO_ICMP: dict[int, tuple[int, int]] = {
    IP_STATUS_SUCCESS: (0, 0),  # Echo Reply
    IP_STATUS_DEST_NET_UNREACHABLE: (3, 0),
    IP_STATUS_DEST_HOST_UNREACHABLE: (3, 1),
    IP_STATUS_DEST_PROT_UNREACHABLE: (3, 2),
    IP_STATUS_DEST_PORT_UNREACHABLE: (3, 3),
    IP_STATUS_PACKET_TOO_BIG: (3, 4),  # Fragmentation Needed and DF Set
    IP_STATUS_BAD_ROUTE: (3, 5),
    IP_STATUS_TTL_EXPIRED_TRANSIT: (11, 0),  # TTL Exceeded in Transit
    IP_STATUS_TTL_EXPIRED_REASSEM: (11, 1),  # Fragment Reassembly Time Exceeded
    IP_STATUS_PARAM_PROBLEM: (12, 0),
    IP_STATUS_SOURCE_QUENCH: (4, 0),
}


def ip_status_to_icmp(status: int) -> tuple[int | None, int | None]:
    """Windows IP_STATUS を (ICMP type, ICMP code) に変換する.

    変換表にない status (タイムアウトや汎用エラーなど、実ICMP応答が無い場合) は
    (None, None) を返す。
    """
    return IP_STATUS_TO_ICMP.get(status, (None, None))
