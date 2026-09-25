from common.iptools.calc.ipv4 import calc
from common.iptools.result import Reason


def _ok_value(ip_str):
    result = calc(ip_str)
    assert result.ok, f"expected ok for {ip_str!r}, got {result.reason}/{result.message}"
    return result.value


def test_basic_cidr():
    info = _ok_value("172.16.201.10/24")
    assert info.network == "172.16.201.0"
    assert info.broadcast == "172.16.201.255"
    assert info.host_min == "172.16.201.1"
    assert info.host_max == "172.16.201.254"
    assert info.num_hosts == 254
    assert info.netmask == "255.255.255.0"
    assert info.wildcard_mask == "0.0.0.255"
    assert info.ip_class == "B"
    assert info.scope == "Private"
    assert info.is_private is True
    assert info.address_hex == "0xAC10C90A"
    assert info.network_hex == "0xAC10C900"
    assert info.broadcast_hex == "0xAC10C9FF"


def test_dotted_netmask_equivalent_to_cidr():
    a = _ok_value("192.168.1.1/24")
    b = _ok_value("192.168.1.1/255.255.255.0")
    assert a.network == b.network
    assert a.prefix_length == b.prefix_length == 24


def test_public_global_scope():
    info = _ok_value("8.8.8.8/32")
    assert info.scope == "Global"
    assert info.is_global is True


def test_slash31_point_to_point_rfc3021():
    info = _ok_value("192.0.2.0/31")
    assert info.num_hosts == 2
    assert info.host_min == "192.0.2.0"
    assert info.host_max == "192.0.2.1"


def test_slash32_host_route_rfc3021():
    info = _ok_value("192.0.2.1/32")
    assert info.num_hosts == 1
    assert info.host_min == info.host_max == "192.0.2.1"


def test_longest_prefix_match_dslite_over_protocol_assignment():
    # 192.0.0.0/29 (DS-Lite) は 192.0.0.0/24 (IETF Protocol Assignments) に包含されるが、
    # より詳細な(prefixの長い)エントリが優先されるべき
    info = _ok_value("192.0.0.5/32")
    assert info.scope == "DS-Lite(Dual-Stack Lite) IPv4 over IPv6"


def test_falls_back_to_broader_range():
    info = _ok_value("192.0.0.100/32")
    assert info.scope == "IETF Protocol Assignments"


def test_link_local_scope():
    info = _ok_value("169.254.1.1/16")
    assert info.scope == "Link Local"
    assert info.is_link_local is True


def test_missing_prefix_reason():
    result = calc("192.168.1.1")
    assert not result.ok
    assert result.reason is Reason.MISSING_PREFIX


def test_invalid_address_reason():
    result = calc("999.1.1.1/24")
    assert not result.ok
    assert result.reason is Reason.INVALID_ADDRESS


def test_invalid_prefix_reason():
    result = calc("192.168.1.1/33")
    assert not result.ok
    assert result.reason is Reason.INVALID_PREFIX


def test_invalid_dotted_mask_reason():
    # 1が連続していない(不正な)ネットマスク
    result = calc("192.168.1.1/255.0.255.0")
    assert not result.ok
    assert result.reason is Reason.INVALID_PREFIX
