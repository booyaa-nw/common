from common.iptools.calc.ipv4 import ip2long
from common.iptools.calc.reserved import load_ipv4_reserved, load_ipv6_reserved, lookup_scope


def test_ipv4_entries_sorted_by_prefix_desc():
    entries = load_ipv4_reserved()
    prefixes = [e.prefix_length for e in entries]
    assert prefixes == sorted(prefixes, reverse=True)


def test_lookup_scope_defaults_to_global():
    scope, rfc = lookup_scope(ip2long("8.8.8.8"), load_ipv4_reserved())
    assert scope == "Global"
    assert rfc == ""


def test_ipv6_reserved_loaded():
    entries = load_ipv6_reserved()
    assert any(e.scope == "Loopback" for e in entries)
