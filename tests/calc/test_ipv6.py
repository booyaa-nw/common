from common.iptools.calc.ipv6 import calc
from common.iptools.result import Reason


def _ok_value(ip_str):
    result = calc(ip_str)
    assert result.ok, f"expected ok for {ip_str!r}, got {result.reason}/{result.message}"
    return result.value


def test_basic():
    info = _ok_value("2001:db8::1/64")
    assert info.network == "2001:db8::"
    assert info.prefix_length == 64
    assert info.scope == "Documentation (TEST-NET equivalent)"


def test_loopback():
    info = _ok_value("::1/128")
    assert info.is_loopback is True
    assert info.scope == "Loopback"


def test_unspecified():
    info = _ok_value("::/128")
    assert info.is_unspecified is True
    assert info.scope == "Unspecified"


def test_link_local():
    info = _ok_value("fe80::1/64")
    assert info.is_link_local is True
    assert info.scope == "Link-local unicast"


def test_unique_local_address():
    info = _ok_value("fd00::1/48")
    assert info.scope == "Unique Local Address (ULA)"
    assert info.is_private is True


def test_global_scope():
    info = _ok_value("2400:8500::1/32")
    assert info.scope == "Global"
    assert info.is_global is True


def test_compressed_and_full_forms():
    info = _ok_value("2001:0db8:0000:0000:0000:0000:0000:0001/32")
    assert info.address == "2001:db8::1"
    assert info.address_full == "2001:0db8:0000:0000:0000:0000:0000:0001"


def test_last_address_of_subnet():
    info = _ok_value("2001:db8::/126")
    assert info.network == "2001:db8::"
    assert info.last_address == "2001:db8::3"
    assert info.num_addresses == 4


def test_missing_prefix_reason():
    result = calc("2001:db8::1")
    assert not result.ok
    assert result.reason is Reason.MISSING_PREFIX


def test_invalid_address_reason():
    result = calc("not-an-ipv6/64")
    assert not result.ok
    assert result.reason is Reason.INVALID_ADDRESS


def test_triple_colon_rejected():
    result = calc("2001:::1/64")
    assert not result.ok
    assert result.reason is Reason.INVALID_ADDRESS


def test_double_double_colon_rejected():
    result = calc("2001::db8::1/64")
    assert not result.ok
    assert result.reason is Reason.INVALID_ADDRESS


def test_invalid_prefix_reason():
    result = calc("2001:db8::1/200")
    assert not result.ok
    assert result.reason is Reason.INVALID_PREFIX
