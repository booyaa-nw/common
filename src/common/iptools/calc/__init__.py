"""iptools.calc: OSの状態に依存しない、純粋なビット計算.

IPv4/IPv6のアドレス・サブネット計算、予約済みアドレス(Special-Purpose Address Registry)の
判定を提供する。標準ライブラリ `ipaddress` は使わず、bit演算で計算する
(ネットワークエンジニアがコードを読んだときに計算の仕組みがそのまま理解できることを重視している)。
"""
