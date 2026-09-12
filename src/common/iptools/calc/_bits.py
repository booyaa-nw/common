"""ビット計算の共通ヘルパー(IPv4/IPv6で共通して使う)."""

from __future__ import annotations


def prefix_mask(prefix: int, bit_length: int) -> int:
    """prefix長から、上位prefixビットが1・残りが0のビットマスク整数を作る.

    例: prefix_mask(24, 32) -> 0xFFFFFF00 (255.255.255.0 相当)
    """
    if prefix <= 0:
        return 0
    if prefix >= bit_length:
        return (1 << bit_length) - 1
    return ((1 << prefix) - 1) << (bit_length - prefix)


def full_mask(bit_length: int) -> int:
    """bit_length分すべて1のビットマスク整数を作る."""
    return (1 << bit_length) - 1
