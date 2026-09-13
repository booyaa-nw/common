"""`common.ping.linux`のテスト.

実ネットワーク・root権限に依存させないため、`ICMPv4Socket`を偽の実装に
差し替えてテストする(実機でのping動作確認は別途ユーザー環境で実施する)。
"""

from __future__ import annotations

import asyncio

import pytest
from icmplib import ICMPError, SocketPermissionError, TimeoutExceeded

import common.ping.linux as linux_module
from common.ping.linux import LinuxPingConfig, ping_once, ping_once_async


class _FakeRawSocket:
    """`ICMPv4Socket.sock`(生ソケット)の代替。DFフラグ設定の呼び出しのみ記録する."""

    def __init__(self) -> None:
        self.setsockopt_calls: list[tuple[int, int, int]] = []

    def setsockopt(self, level: int, optname: int, value: int) -> None:
        self.setsockopt_calls.append((level, optname, value))


class _FakeReply:
    """`icmplib.ICMPReply`の代替。`raise_for_status`の実際の分岐ロジックのみ再現する."""

    def __init__(self, *, type_: int, code: int, source: str | None, rtt: float = 0.01) -> None:
        self.type = type_
        self.code = code
        self.source = source
        self.time = rtt  # request.time(実装からは常に0)からの差分がそのままrttになる

    def raise_for_status(self) -> None:
        from icmplib import ICMPv4DestinationUnreachable, ICMPv4TimeExceeded

        if self.type == 0:
            return
        if self.type == 3:
            raise ICMPv4DestinationUnreachable(self)
        if self.type == 11:
            raise ICMPv4TimeExceeded(self)
        raise ICMPError(f"type={self.type}, code={self.code}", self)


class _FakeICMPv4Socket:
    """`common.ping.linux.ICMPv4Socket`の代替。send/receiveの結果をテストごとに差し替える."""

    def __init__(
        self,
        *,
        reply: _FakeReply | None = None,
        raise_on_send: Exception | None = None,
        raise_on_receive: Exception | None = None,
    ) -> None:
        self.sock = _FakeRawSocket()
        self._reply = reply
        self._raise_on_send = raise_on_send
        self._raise_on_receive = raise_on_receive
        self.sent_requests: list = []
        self.closed = False

    def send(self, request) -> None:
        if self._raise_on_send is not None:
            raise self._raise_on_send
        self.sent_requests.append(request)

    def receive(self, request, timeout):
        if self._raise_on_receive is not None:
            raise self._raise_on_receive
        return self._reply

    def close(self) -> None:
        self.closed = True


def _patch_socket_factory(monkeypatch, fake_socket: _FakeICMPv4Socket):
    """`ICMPv4Socket(...)`の呼び出しを、常に同じ`fake_socket`を返すように差し替える."""

    def _factory(*args, **kwargs):
        return fake_socket

    monkeypatch.setattr(linux_module, "ICMPv4Socket", _factory)


def _config(**overrides) -> LinuxPingConfig:
    base = dict(ttl=64, timeout=1.0, data_size=32, df=False)
    base.update(overrides)
    return LinuxPingConfig(**base)


def test_success_reply_returns_ok_with_rtt_and_reply_from(monkeypatch):
    fake = _FakeICMPv4Socket(reply=_FakeReply(type_=0, code=0, source="1.1.1.1", rtt=0.012))
    _patch_socket_factory(monkeypatch, fake)

    result = ping_once("1.1.1.1", _config())

    assert result.ok is True
    assert result.rtt == pytest.approx(0.012)
    assert result.icmp_type == 0
    assert result.icmp_code == 0
    assert result.reply_from == "1.1.1.1"
    assert fake.closed is True  # ソケットが必ずcloseされること


def test_timeout_returns_type_no_reply(monkeypatch):
    fake = _FakeICMPv4Socket(raise_on_receive=TimeoutExceeded(1.0))
    _patch_socket_factory(monkeypatch, fake)

    result = ping_once("192.0.2.1", _config(timeout=1.0))

    assert result.ok is False
    assert result.rtt is None
    assert result.icmp_type == 98  # TYPE_NO_REPLY
    assert result.icmp_code == 0
    assert result.reply_from is None


def test_ttl_exceeded_reports_real_icmp_type_and_reply_from(monkeypatch):
    # 中継ルータがTTL超過(ICMP type=11)で応答したケース。reply_fromは宛先自身ではなく
    # 実際に応答した中継ルータのアドレスになる。
    fake = _FakeICMPv4Socket(reply=_FakeReply(type_=11, code=0, source="10.0.0.1", rtt=0.005))
    _patch_socket_factory(monkeypatch, fake)

    result = ping_once("8.8.8.8", _config(ttl=1))

    assert result.ok is False
    assert result.rtt == pytest.approx(0.005)
    assert result.icmp_type == 11
    assert result.icmp_code == 0
    assert result.reply_from == "10.0.0.1"


def test_destination_unreachable_reports_real_icmp_type(monkeypatch):
    fake = _FakeICMPv4Socket(reply=_FakeReply(type_=3, code=1, source="192.168.1.1", rtt=0.003))
    _patch_socket_factory(monkeypatch, fake)

    result = ping_once("192.168.1.99", _config())

    assert result.ok is False
    assert result.icmp_type == 3
    assert result.icmp_code == 1
    assert result.reply_from == "192.168.1.1"


def test_socket_permission_error_returns_type_unknown_error_with_hint(monkeypatch):
    def _factory(*args, **kwargs):
        raise SocketPermissionError(False)

    monkeypatch.setattr(linux_module, "ICMPv4Socket", _factory)

    result = ping_once("1.1.1.1", _config())

    assert result.ok is False
    assert result.icmp_type == 99  # TYPE_UNKNOWN_ERROR
    assert result.reply_from is None
    assert "権限" in result.message
    assert "ping_group_range" in result.message


def test_send_failure_returns_type_unknown_error(monkeypatch):
    from icmplib import ICMPSocketError

    fake = _FakeICMPv4Socket(raise_on_send=ICMPSocketError("boom"))
    _patch_socket_factory(monkeypatch, fake)

    result = ping_once("not-an-ip", _config())

    assert result.ok is False
    assert result.icmp_type == 99  # TYPE_UNKNOWN_ERROR
    assert result.reply_from is None
    assert fake.closed is True


def test_df_true_sets_pmtudisc_do(monkeypatch):
    fake = _FakeICMPv4Socket(reply=_FakeReply(type_=0, code=0, source="1.1.1.1"))
    _patch_socket_factory(monkeypatch, fake)

    ping_once("1.1.1.1", _config(df=True))

    assert fake.sock.setsockopt_calls == [(0, 10, 2)]  # IPPROTO_IP, IP_MTU_DISCOVER, IP_PMTUDISC_DO


def test_df_false_sets_pmtudisc_want(monkeypatch):
    fake = _FakeICMPv4Socket(reply=_FakeReply(type_=0, code=0, source="1.1.1.1"))
    _patch_socket_factory(monkeypatch, fake)

    ping_once("1.1.1.1", _config(df=False))

    assert fake.sock.setsockopt_calls == [(0, 10, 1)]  # IPPROTO_IP, IP_MTU_DISCOVER, IP_PMTUDISC_WANT


def test_ping_once_async_offloads_to_thread(monkeypatch):
    fake = _FakeICMPv4Socket(reply=_FakeReply(type_=0, code=0, source="1.1.1.1", rtt=0.02))
    _patch_socket_factory(monkeypatch, fake)

    result = asyncio.run(ping_once_async("1.1.1.1", _config()))

    assert result.ok is True
    assert result.rtt == pytest.approx(0.02)
