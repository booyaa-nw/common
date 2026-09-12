from common.ping.base import (
    IP_STATUS_DEST_HOST_UNREACHABLE,
    IP_STATUS_PACKET_TOO_BIG,
    IP_STATUS_REQ_TIMED_OUT,
    IP_STATUS_TTL_EXPIRED_TRANSIT,
    ip_status_to_icmp,
)


def test_ttl_expired_maps_to_icmp_type_11():
    icmp_type, icmp_code = ip_status_to_icmp(IP_STATUS_TTL_EXPIRED_TRANSIT)
    assert icmp_type == 11
    assert icmp_code == 0


def test_packet_too_big_maps_to_fragmentation_needed():
    # --size/--df によるMTU試験で重要になる変換: 正規表現ベースのパースでは
    # 検出できなかった「フラグメント禁止での分割不可」に対応する。
    icmp_type, icmp_code = ip_status_to_icmp(IP_STATUS_PACKET_TOO_BIG)
    assert (icmp_type, icmp_code) == (3, 4)


def test_dest_host_unreachable_mapping():
    assert ip_status_to_icmp(IP_STATUS_DEST_HOST_UNREACHABLE) == (3, 1)


def test_timeout_status_has_no_icmp_mapping():
    # タイムアウトは実ICMP応答が無いため変換表に含まれず (None, None) になる
    assert ip_status_to_icmp(IP_STATUS_REQ_TIMED_OUT) == (None, None)


def test_unknown_status_returns_none_none():
    assert ip_status_to_icmp(999999) == (None, None)
