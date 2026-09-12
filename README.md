# common

booyaa配下の各ツールから使う共通ライブラリ。現状は `iptools`（IPアドレス計算・ネットワーク情報取得）のみを提供する。

`C:\opt\booyaa_old\booyaa\common\iptools.py`、および`C:\opt\booyaa_old\booyaa\ipcalc\ipv4.py`等の
ビット計算ロジックをリファレンスに、責務ごとに再構成したもの。

## 設計方針

- **例外を投げない**。全公開関数は `iptools.result.IPToolsResult` を返す。`ok=True` のときだけ
  `value` に意味があり、`ok=False` のときだけ `reason`（`Reason` Enum）/`message` に意味がある。
  想定外の例外も各関数の境界（`@safe_call`）で捕捉し `Reason.UNEXPECTED_ERROR` に変換するため、
  呼び出し側は基本的に `result.ok` を見るだけでよい。
- 「判定の答えそのものがtrue/falseである関数」（`is_my_nic_addr`等）では、`value` に生のbool値を
  直接入れない。`ok=True, value=False` という形は「ok」の直感（そのまま使ってよい）と紛れやすいため、
  意味の分かる名前を持つ小さなdataclassに包む（例: `value.is_mine`）。
- **`ipaddress`は実行時コードでは使わない**。IPv4/IPv6の計算はすべてbit演算で行う。ネットワーク
  エンジニアがコードを読んだときに、サブネット計算の仕組みがそのまま理解できることを重視している。
  正しさの担保として、テストコード（`tests/calc/test_oracle_ipaddress.py`）でのみ`ipaddress`を
  「大量のテストケースの正解データを作る道具」として使い、手組み実装の結果と突き合わせている
  （本体コードは一切importしない。`ipaddress`の依存は`dependency-groups.dev`にも追加していない
  — 標準ライブラリなので追加不要）。
- `/31`, `/32` は RFC3021 準拠（ネットワークアドレス・ブロードキャストアドレスも含めて使用可能）。

## モジュール構成

```
iptools/
├── result.py            # IPToolsResult / Reason（全モジュール共通の戻り値型）
├── calc/                 # 純粋関数のみ。OS状態に依存しない
│   ├── _bits.py            # ビットマスク生成等、v4/v6共通のヘルパー
│   ├── ipv4.py             # IPv4計算 (ip2long/long2ip, cidr<->netmask変換, network/broadcast/host range)
│   ├── ipv6.py             # IPv6計算 (128bit整数での計算, RFC5952準拠の圧縮表記)
│   ├── auto.py             # IPv4/IPv6自動判定
│   └── reserved.py         # Special-Purpose Address Registry (v4/v6 CSV, 最長一致lookup)
├── host/                 # 副作用あり。socket/psutil等でOSに問い合わせる
│   ├── interfaces.py       # get_my_nics, is_my_nic_addr（自ホストのNIC/IP一覧）
│   ├── routing.py          # get_src_addr, get_my_default_addr（宛先に対する送信元IP）
│   └── resolve.py          # is_fqdn, is_resolve（FQDN検証・名前解決）
├── validate.py           # is_valid_dst, is_valid_src（calc/hostを組み合わせた妥当性判定）
└── data/
    ├── ipv4_reserved.csv
    └── ipv6_reserved.csv
```

`calc`（決定的・OS非依存）と`host`（OS状態に依存）を分けているのは、将来pingツールのようなものを
作る際、「宛先に対する送信元IP・出力インタフェースを`host.routing`から取得し、`calc.ipv4`/`calc.ipv6`
でアドレスを検証・整形し、`validate`で最終的な妥当性を判定してから送信する」という流れがそのまま
コードの依存関係になることを意図している。

## 使用例

```python
from common.iptools.calc import ipv4

result = ipv4.calc("172.16.201.10/24")
if not result.ok:
    print(result.reason, result.message)
else:
    info = result.value
    print(info.network, info.broadcast, info.num_hosts)
```

```python
from common.iptools.host.interfaces import is_my_nic_addr

result = is_my_nic_addr("192.168.1.10")
if not result.ok:
    print("判定不能:", result.reason, result.message)
elif result.value.is_mine:
    print("自分のIPです (interface:", result.value.matched_interface, ")")
else:
    print("自分のIPではありません")
```

## 旧実装からの主な変更点

- `common/iptools.py`（NIC取得・FQDN検証等）と `ipcalc/ipv4.py`・`ipv6.py`（ビット計算）に分かれて
  いた実装を、責務ごとに再構成した `iptools` パッケージへ統合。
- 全関数が例外の代わりに `IPToolsResult`（`ok`/`value`/`reason`/`message`）を返すよう統一。
- IPv6は`ipv6.py`（importタイプミス: `booya.ipcalc.ipv4`）と`ipv6_inprogress.py`（末尾に重複コード）
  の2系統が中途半端に存在していたのを、1つの実装に整理・修正。
- `/31`, `/32` を RFC3021 準拠に修正（旧実装は`/31`のホスト数を0として扱っていた）。
- `169.254.0.0/24`という誤ったCIDR（正しくは`/16`, RFC3927）を修正。
- `ipmask2cidr`が`self.is_ip()`を引数ではなく`self.ip`に対して呼んでいたバグを修正（新実装は
  引数の文字列を直接検証する）。
- `is_valid_dst`/`is_valid_src`が返していた0/1/2のマジックナンバーを、`Reason` Enumに置き換え。

## 開発

```powershell
cd tools/common
uv run pytest
```
