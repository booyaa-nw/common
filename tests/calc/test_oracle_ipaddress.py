"""正しさの担保用: 標準ライブラリ ipaddress を「正解データを作る道具」としてのみ使うテスト.

common.iptools 本体のコード(src/common/iptools/配下)はどのファイルもipaddressをimportしない。
このテストファイルの中だけで、大量のケースに対する期待値をipaddressで機械的に生成し、
手組みのbit計算実装(common.iptools.calc.ipv4/ipv6)の結果と突き合わせる。
"""

import ipaddress
import random

from common.iptools.calc.ipv4 import calc as calc_ipv4
from common.iptools.calc.ipv6 import calc as calc_ipv6

IPV4_FIXED_CASES = [
    "10.1.2.3/8",
    "172.16.201.10/24",
    "192.168.1.1/24",
    "203.0.113.5/30",
    "198.51.100.7/29",
    "8.8.8.8/32",
    "0.0.0.0/0",
    "192.0.2.0/31",
    "192.0.2.1/32",
    "169.254.5.5/16",
]


def test_ipv4_matches_ipaddress_for_fixed_cases():
    for case in IPV4_FIXED_CASES:
        ours = calc_ipv4(case)
        assert ours.ok, f"{case}: {ours.reason}/{ours.message}"

        ref_iface = ipaddress.ip_interface(case)
        ref_net = ref_iface.network

        assert ours.value.network == str(ref_net.network_address), case
        assert ours.value.netmask == str(ref_net.netmask), case

        if ref_net.prefixlen < 31:
            assert ours.value.broadcast == str(ref_net.broadcast_address), case
            # list(ref_net.hosts())は/0のような巨大なネットワークだと大量のアドレスを
            # 列挙してしまうため、算術的に境界値だけ求めてoursと突き合わせる
            expected_host_min = ipaddress.ip_address(int(ref_net.network_address) + 1)
            expected_host_max = ipaddress.ip_address(int(ref_net.broadcast_address) - 1)
            expected_num_hosts = ref_net.num_addresses - 2
            assert ours.value.host_min == str(expected_host_min), case
            assert ours.value.host_max == str(expected_host_max), case
            assert ours.value.num_hosts == expected_num_hosts, case


def test_ipv4_matches_ipaddress_for_random_cases():
    rng = random.Random(12345)
    for _ in range(300):
        octets = [rng.randint(0, 255) for _ in range(4)]
        prefix = rng.randint(0, 32)
        case = f"{'.'.join(map(str, octets))}/{prefix}"

        ours = calc_ipv4(case)
        assert ours.ok, f"{case}: {ours.reason}/{ours.message}"

        ref_net = ipaddress.ip_interface(case).network
        assert ours.value.network == str(ref_net.network_address), case
        assert ours.value.network_int == int(ref_net.network_address), case
        assert int(ours.value.netmask.replace(".", "")) or True  # netmaskは下のnetmask比較で十分
        assert ours.value.netmask == str(ref_net.netmask), case


IPV6_FIXED_CASES = [
    "2001:db8::1/64",
    "2001:db8::/32",
    "fe80::1/64",
    "::1/128",
    "::/0",
    "2001:db8::/126",
    "fd00:1234:5678::1/48",
]


def test_ipv6_matches_ipaddress_for_fixed_cases():
    for case in IPV6_FIXED_CASES:
        ours = calc_ipv6(case)
        assert ours.ok, f"{case}: {ours.reason}/{ours.message}"

        ref_iface = ipaddress.ip_interface(case)
        ref_net = ref_iface.network

        assert ours.value.network_int == int(ref_net.network_address), case
        assert ours.value.address_int == int(ref_iface.ip), case
        assert ours.value.last_address_int == int(ref_net.broadcast_address), case
        assert ours.value.num_addresses == ref_net.num_addresses, case
        # compressed表記の一致(標準ライブラリの正規化と同じになるはず)
        assert ours.value.address == ref_iface.ip.compressed, case
        assert ours.value.network == ref_net.network_address.compressed, case


def test_ipv6_matches_ipaddress_for_random_cases():
    rng = random.Random(54321)
    for _ in range(300):
        groups = [format(rng.randint(0, 0xFFFF), "x") for _ in range(8)]
        prefix = rng.randint(0, 128)
        case = f"{':'.join(groups)}/{prefix}"

        ours = calc_ipv6(case)
        assert ours.ok, f"{case}: {ours.reason}/{ours.message}"

        ref_net = ipaddress.ip_interface(case).network
        assert ours.value.network_int == int(ref_net.network_address), case
        assert ours.value.last_address_int == int(ref_net.broadcast_address), case
        assert ours.value.num_addresses == ref_net.num_addresses, case
