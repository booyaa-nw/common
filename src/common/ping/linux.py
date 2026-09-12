"""Linux: `icmplib` を用いた ICMP echo 実装 (未実装・後日対応).

`tools/mping`でのリニューアル時、ユーザー指示によりLinux実装は対象外
(後回し)とされたスタブをそのまま移植したもの(移植元: `mping/ping/linux.py`)。
`icmplib.async_ping` はネイティブの非同期APIを提供するため、実装時は
Windows側のような `asyncio.to_thread` オフロードは不要になる見込み。
"""

from __future__ import annotations

from common.ping.base import PingResult


class LinuxPingConfig:
    def __init__(self, ttl: int, timeout: float, data_size: int, df: bool) -> None:
        self.ttl = ttl
        self.timeout = timeout
        self.data_size = data_size
        self.df = df


async def ping_once_async(dst_ip: str, config: LinuxPingConfig) -> PingResult:
    """`icmplib.async_ping` を使った実装 (TODO: 未実装).

    呼び出すと `NotImplementedError` を送出する。
    """
    raise NotImplementedError(
        "Linux向けping実装 (icmplib) は未実装です。"
    )
