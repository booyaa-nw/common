"""Linux: `icmplib` を用いた ICMP echo 実装.

`icmplib`の低レベル同期API(`ICMPv4Socket`+`ICMPRequest`)を`asyncio.to_thread`で
オフロードする形で使う(Windows実装`common.ping.windows`と同じ「ブロッキングする
呼び出しをスレッドオフロード」構成)。Windows実装と同じく、1回のpingごとに
`PingResult`を1つ返すインターフェースに合わせている。

`icmplib.async_ping`(複数回・集計して`Host`を返す高レベルAPI)や、`icmplib`が
提供する非同期ソケット(`AsyncSocket`)ではなく、あえて同期API+`to_thread`を
使うのは、以下2点の理由による。

1. 呼び出し側(`mping.runner.PingRunner`)は1回のpingごとに`PingTarget`の状態
   (成功/失敗カウント・履歴・直近RTT)を更新する設計であり、`Host`のような
   複数回分の集計結果ではなく1回分の結果が必要(`async_ping`不採用の理由)。
2. `icmplib.AsyncSocket.receive`は`asyncio`の`loop.sock_recv`を使う都合上、
   実際に応答したホストのアドレス(`reply.source`)を**常にNoneにしてしまう**
   (icmplib公式docstringにも明記された既知の制約)。TTL超過(ICMP type==11)時に
   中継ルータのアドレスを`reply_from`として取得する必要があるため、この情報が
   正しく得られる同期API(`ICMPv4Socket.receive`)側を使う必要がある。

権限について: Linuxでの生ICMPソケット(`SOCK_RAW`)作成には通常root権限が必要だが、
`icmplib`は`privileged=False`指定時、rootを必要としない`SOCK_DGRAM`ベースの
非特権ICMPソケットを使う(Linux固有の機能。多くのディストリビューションで
`net.ipv4.ping_group_range`が全ユーザーを許可する既定値になっており動作する)。
Windows実装(`iphlpapi.dll`経由、admin権限不要)との体験統一のため、本実装は
既定で`privileged=False`とする。カーネル設定でこの非特権ICMPが無効化されている
環境では、ソケット作成に失敗し`SocketPermissionError`となる(その場合は
`sudo`で実行するか、`sysctl -w net.ipv4.ping_group_range="0 2147483647"`等で
非特権ICMPを有効化する必要がある)。

DF(Don't Fragment)フラグについて: `icmplib`自体はTTL・TOS(traffic_class)のみを
サポートしDFフラグの設定機能を持たないため、生ソケット(`ICMPv4Socket.sock`)に対し
直接`IP_MTU_DISCOVER`(`IP_PMTUDISC_DO`)を設定することで実現する。この定数は
Python標準の`socket`モジュールには公開されていない(Linux固有の`<linux/in.h>`
定義)ため、本モジュールで値を直接定義する。
"""

from __future__ import annotations

import asyncio
import random
import socket
from dataclasses import dataclass

from icmplib import (
    ICMPError,
    ICMPRequest,
    ICMPSocketError,
    ICMPv4Socket,
    SocketPermissionError,
    TimeoutExceeded,
)

from common.ping.base import (
    CODE_NONE,
    ICMP_TYPE_ECHO_REPLY,
    TYPE_NO_REPLY,
    TYPE_UNKNOWN_ERROR,
    PingResult,
)

# <linux/in.h> 定義。Python標準の`socket`モジュールには公開されていないため、
# ここで直接定義する(値はLinuxカーネルの安定ABIであり変更されない)。
_IP_MTU_DISCOVER = 10
_IP_PMTUDISC_WANT = 1  # カーネルの既定動作(必要に応じてフラグメント許可)
_IP_PMTUDISC_DO = 2  # DFを立てる(経路上でフラグメントが必要な場合は失敗させる)


@dataclass
class LinuxPingConfig:
    ttl: int
    timeout: float
    data_size: int
    df: bool
    privileged: bool = False


def _apply_df(raw_sock: socket.socket, df: bool) -> None:
    """DF(Don't Fragment)フラグを生ソケットに設定する.

    `icmplib`はTTL/TOSのみをサポートしDFフラグの設定手段を持たないため、
    `ICMPv4Socket.sock`で取得できる生ソケットに対し直接設定する。
    """
    try:
        value = _IP_PMTUDISC_DO if df else _IP_PMTUDISC_WANT
        raw_sock.setsockopt(socket.IPPROTO_IP, _IP_MTU_DISCOVER, value)
    except OSError:
        # 一部環境(コンテナ等)で`IP_MTU_DISCOVER`が使えない場合があるが、
        # DF設定はMTU試験用のオプション機能のため、失敗してもping自体は続行する。
        pass


def ping_once(dst_ip: str, config: LinuxPingConfig) -> PingResult:
    """指定した宛先IPに対して1回 ICMP echo を送信する(同期・ブロッキング).

    非同期実行は呼び出し側 (`ping_once_async`) が `asyncio.to_thread` で
    スレッドオフロードする前提で、ここでは同期APIとして実装する
    (Windows実装 `common.ping.windows.ping_once` と対になる構成)。
    """
    try:
        icmp_sock = ICMPv4Socket(privileged=config.privileged)
    except SocketPermissionError as exc:
        return PingResult(
            ok=False,
            rtt=None,
            icmp_type=TYPE_UNKNOWN_ERROR,
            icmp_code=CODE_NONE,
            reply_from=None,
            message=(
                "ICMPソケットの作成に失敗しました(権限不足)。root権限で実行するか、"
                '`sysctl -w net.ipv4.ping_group_range="0 2147483647"`等で'
                f"非特権ICMPを有効化してください: {exc}"
            ),
        )
    except OSError as exc:
        return PingResult(
            ok=False,
            rtt=None,
            icmp_type=TYPE_UNKNOWN_ERROR,
            icmp_code=CODE_NONE,
            reply_from=None,
            message=f"ICMPソケットの作成に失敗しました: {exc}",
        )

    try:
        _apply_df(icmp_sock.sock, config.df)

        request = ICMPRequest(
            destination=dst_ip,
            id=random.randint(0, 0xFFFF),
            sequence=0,
            payload_size=max(config.data_size, 0),
            ttl=config.ttl,
        )

        try:
            icmp_sock.send(request)
        except (ICMPSocketError, OSError) as exc:
            # 宛先文字列の解決失敗(不正なIPアドレス等)・経路なし等、送信自体の失敗。
            # 実ICMP応答は無いため疑似type/codeを使う(Windows実装の`inet_addr`
            # 失敗時・`IcmpSendEcho`失敗時の扱いと同じ)。
            return PingResult(
                ok=False,
                rtt=None,
                icmp_type=TYPE_UNKNOWN_ERROR,
                icmp_code=CODE_NONE,
                reply_from=None,
                message=f"send failed: {exc}",
            )

        try:
            reply = icmp_sock.receive(request, config.timeout)
        except TimeoutExceeded:
            # 純粋なタイムアウト(応答を一切受信できなかった)。Windows実装と同様、
            # 実ICMP応答が無いため疑似type/code(TYPE_NO_REPLY)で埋める。
            return PingResult(
                ok=False, rtt=None, icmp_type=TYPE_NO_REPLY, icmp_code=CODE_NONE, reply_from=None, message="timeout"
            )
        except (ICMPSocketError, OSError) as exc:
            return PingResult(
                ok=False,
                rtt=None,
                icmp_type=TYPE_UNKNOWN_ERROR,
                icmp_code=CODE_NONE,
                reply_from=None,
                message=f"receive failed: {exc}",
            )

        try:
            reply.raise_for_status()
        except ICMPError:
            # タイムアウト以外の実ICMP応答(到達不能・TTL超過等)。
            # `reply.source`は実際に応答したホスト(TTL超過時は中継ルータ)のアドレス。
            rtt = reply.time - request.time
            return PingResult(
                ok=False,
                rtt=rtt,
                icmp_type=reply.type,
                icmp_code=reply.code,
                reply_from=reply.source,
                message=f"icmp_type={reply.type}, icmp_code={reply.code}",
            )

        rtt = reply.time - request.time
        return PingResult(
            ok=True,
            rtt=rtt,
            icmp_type=ICMP_TYPE_ECHO_REPLY,
            icmp_code=0,
            reply_from=reply.source,
        )
    finally:
        icmp_sock.close()


async def ping_once_async(dst_ip: str, config: LinuxPingConfig) -> PingResult:
    """`ping_once`(同期・ブロッキング)を`asyncio.to_thread`でオフロードする."""
    return await asyncio.to_thread(ping_once, dst_ip, config)
