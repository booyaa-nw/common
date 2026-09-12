"""OS判定によるping実装のディスパッチ.

`tools/mping` で自己完結モジュールとして実装・pytest済みの上で本モジュール
(`common.ping`)へ移植したもの(移植元: `mping/ping/__init__.py`)。
"""

from __future__ import annotations

import asyncio
import sys

from common.ping.base import PingResult

__all__ = ["ping_async", "PingResult"]


async def ping_async(
    dst_ip: str,
    *,
    ttl: int,
    timeout: float,
    data_size: int,
    df: bool,
) -> PingResult:
    """OSに応じたping実装を非同期に実行する.

    Windows: ブロッキングする ctypes 呼び出しを `asyncio.to_thread` でオフロード。
    Linux: `icmplib` のネイティブ非同期APIを利用予定(現時点では未実装)。
    """
    if sys.platform == "win32":
        from common.ping.windows import WindowsPingConfig, ping_once

        config = WindowsPingConfig(ttl=ttl, timeout_ms=int(timeout * 1000), data_size=data_size, df=df)
        return await asyncio.to_thread(ping_once, dst_ip, config)

    from common.ping.linux import LinuxPingConfig, ping_once_async

    linux_config = LinuxPingConfig(ttl=ttl, timeout=timeout, data_size=data_size, df=df)
    return await ping_once_async(dst_ip, linux_config)
