import socket
from unittest.mock import patch

from common.iptools.host.resolve import is_fqdn, is_resolve


def test_is_fqdn_valid():
    result = is_fqdn("example.com")
    assert result.ok
    assert result.value.is_valid is True


def test_is_fqdn_leading_dot_invalid():
    result = is_fqdn(".example.com")
    assert result.ok
    assert result.value.is_valid is False


def test_is_fqdn_strict_rejects_underscore():
    result = is_fqdn("my_host.example.com", strict=True)
    assert result.ok
    assert result.value.is_valid is False


def test_is_fqdn_loose_allows_underscore():
    result = is_fqdn("my_host.example.com", strict=False)
    assert result.ok
    assert result.value.is_valid is True


def test_is_resolve_success():
    with patch("common.iptools.host.resolve.socket.getaddrinfo") as mocked:
        mocked.return_value = [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
        result = is_resolve("example.com")

    assert result.ok
    assert result.value.resolvable is True
    assert result.value.addresses == ("93.184.216.34",)


def test_is_resolve_failure_is_a_valid_negative_answer():
    with patch("common.iptools.host.resolve.socket.getaddrinfo") as mocked:
        mocked.side_effect = socket.gaierror("not found")
        result = is_resolve("this-does-not-exist.invalid")

    # 名前解決できないこと自体は正常に判定できているので ok=True
    assert result.ok
    assert result.value.resolvable is False
