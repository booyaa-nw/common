from unittest.mock import patch

from common.iptools.result import IPToolsResult, Reason
from common.iptools.validate import is_valid_dst, is_valid_src


def test_is_valid_dst_accepts_ip_directly():
    result = is_valid_dst("8.8.8.8")
    assert result.ok


def test_is_valid_dst_invalid_fqdn_format():
    result = is_valid_dst(".bad-host")
    assert not result.ok
    assert result.reason is Reason.INVALID_FQDN


def test_is_valid_dst_not_resolvable():
    with patch("common.iptools.validate.is_resolve") as mocked:
        from common.iptools.host.resolve import ResolveCheck

        mocked.return_value = IPToolsResult.success(ResolveCheck(resolvable=False, addresses=()))
        result = is_valid_dst("this-does-not-exist.example")

    assert not result.ok
    assert result.reason is Reason.NOT_RESOLVABLE


def test_is_valid_src_invalid_format():
    result = is_valid_src("not-an-ip")
    assert not result.ok
    assert result.reason is Reason.INVALID_ADDRESS


def test_is_valid_src_not_my_address():
    with patch("common.iptools.validate.is_my_nic_addr") as mocked:
        from common.iptools.host.interfaces import MembershipCheck

        mocked.return_value = IPToolsResult.success(MembershipCheck(is_mine=False, matched_interface=None))
        result = is_valid_src("8.8.8.8")

    assert not result.ok
    assert result.reason is Reason.NOT_MY_ADDRESS


def test_is_valid_src_ok_when_my_address():
    with patch("common.iptools.validate.is_my_nic_addr") as mocked:
        from common.iptools.host.interfaces import MembershipCheck

        mocked.return_value = IPToolsResult.success(
            MembershipCheck(is_mine=True, matched_interface="eth0")
        )
        result = is_valid_src("192.168.1.10")

    assert result.ok
