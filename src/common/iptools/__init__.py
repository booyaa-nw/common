"""iptools: IPアドレス計算とネットワーク情報取得のための共通ライブラリ.

- `iptools.calc` : 純粋なビット計算(IPv4/IPv6のアドレス・サブネット計算、予約アドレス判定)。
  OSの状態に依存しない。
- `iptools.host` : OSに問い合わせる機能(NIC/IP一覧取得、宛先に対する送信元IP判定、名前解決)。
- `iptools.validate` : calc/hostを組み合わせた、入力の妥当性判定。

全ての公開関数は `iptools.result.IPToolsResult` を返す。例外は投げない
(想定外の例外は各関数の境界で捕捉し `Reason.UNEXPECTED_ERROR` として返す)。
"""

__version__ = "0.1.0"
