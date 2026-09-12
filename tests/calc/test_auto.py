from common.iptools.calc.auto import calc
from common.iptools.calc.ipv4 import IPv4Info
from common.iptools.calc.ipv6 import IPv6Info


def test_auto_detect_ipv4():
    result = calc("192.168.1.1/24")
    assert result.ok
    assert isinstance(result.value, IPv4Info)


def test_auto_detect_ipv6():
    result = calc("2001:db8::1/64")
    assert result.ok
    assert isinstance(result.value, IPv6Info)
