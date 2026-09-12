"""宛先に対する送信元IP・経路情報の取得."""

from __future__ import annotations

import socket

from common.iptools.result import IPToolsResult, Reason, safe_call


@safe_call
def get_src_addr(dst: str) -> IPToolsResult[str]:
    """宛先(IPアドレス、または名前解決済みの文字列)に対して、OSが選択する送信元IPアドレスを取得する.

    UDPソケットをconnect(実際にはパケットは送信しない)することで、OSのルーティング判断により
    送信元IPアドレスを決定させる。宛先がFQDNの場合は事前に名前解決しておくこと
    (`iptools.host.resolve.is_resolve` 等)。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((dst, 0))
        src = sock.getsockname()[0]
    except OSError as exc:
        return IPToolsResult.failure(
            Reason.NO_ROUTE, f"宛先 {dst!r} に対する経路を決定できませんでした: {exc}"
        )
    finally:
        sock.close()

    return IPToolsResult.success(src)


@safe_call
def get_my_default_addr() -> IPToolsResult[str]:
    """自ホストのデフォルトのIPアドレスを取得する(ホスト名の名前解決結果)."""
    return IPToolsResult.success(socket.gethostbyname(socket.gethostname()))


@safe_call
def get_my_hostname() -> IPToolsResult[str]:
    """自ホストのホスト名を取得する."""
    return IPToolsResult.success(socket.gethostname())
