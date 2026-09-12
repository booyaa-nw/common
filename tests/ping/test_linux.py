import asyncio

import pytest

from common.ping.linux import LinuxPingConfig, ping_once_async


def test_ping_once_async_raises_not_implemented():
    config = LinuxPingConfig(ttl=64, timeout=1.0, data_size=32, df=False)
    with pytest.raises(NotImplementedError):
        asyncio.run(ping_once_async("127.0.0.1", config))
