from unittest.mock import MagicMock, patch

from common.iptools.host.interfaces import get_my_nics, is_my_nic_addr
from common.iptools.result import Reason


def _fake_snic(family, address):
    snic = MagicMock()
    snic.family = family
    snic.address = address
    return snic


def test_get_my_nics_parses_psutil_output():
    import socket

    fake_addrs = {
        "eth0": [
            _fake_snic(socket.AF_INET, "192.168.1.10"),
            _fake_snic(socket.AF_INET6, "fe80::1%eth0"),
        ],
        "lo": [
            _fake_snic(socket.AF_INET, "127.0.0.1"),
        ],
    }
    with patch("common.iptools.host.interfaces.psutil.net_if_addrs", return_value=fake_addrs):
        result = get_my_nics()

    assert result.ok
    ipv4_addrs = {n.address for n in result.value.ipv4}
    ipv6_addrs = {n.address for n in result.value.ipv6}
    assert ipv4_addrs == {"192.168.1.10", "127.0.0.1"}
    assert ipv6_addrs == {"fe80::1"}  # scope idが取り除かれていること


def test_is_my_nic_addr_true_when_matching():
    with patch("common.iptools.host.interfaces.get_my_nics") as mocked:
        from common.iptools.host.interfaces import MyNics, NicAddress
        from common.iptools.result import IPToolsResult

        mocked.return_value = IPToolsResult.success(
            MyNics(ipv4=(NicAddress("eth0", "192.168.1.10"),), ipv6=())
        )
        result = is_my_nic_addr("192.168.1.10")

    assert result.ok
    assert result.value.is_mine is True
    assert result.value.matched_interface == "eth0"


def test_is_my_nic_addr_false_when_not_matching():
    with patch("common.iptools.host.interfaces.get_my_nics") as mocked:
        from common.iptools.host.interfaces import MyNics
        from common.iptools.result import IPToolsResult

        mocked.return_value = IPToolsResult.success(MyNics(ipv4=(), ipv6=()))
        result = is_my_nic_addr("8.8.8.8")

    # 判定は正常にできている(ok=True)が、答えとしては「自分のIPではない」
    assert result.ok
    assert result.value.is_mine is False


def test_is_my_nic_addr_invalid_format():
    result = is_my_nic_addr("not-an-ip")
    assert not result.ok
    assert result.reason is Reason.INVALID_ADDRESS
