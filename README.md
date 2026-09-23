# common

booyaa配下の各ツールから使う共通ライブラリ。`iptools`（IPアドレス計算・ネットワーク情報取得）に加え、
`cli`（CLI引数解析基盤）・`logging`（動作ログ基盤）・`ping`（ICMP echo基盤）・`ftp`（受信専用の
簡易FTPサーバ基盤）を提供する。

`iptools`は`C:\opt\booyaa_old\booyaa\common\iptools.py`、および`C:\opt\booyaa_old\booyaa\ipcalc\ipv4.py`等の
ビット計算ロジックをリファレンスに、責務ごとに再構成したもの。

`cli`・`logging`・`ping`は、`tools/mping`のリニューアル時に「mping側で自己完結した形でまず実装・
テスト・(可能なものは)実機確認を済ませ、その結果を`common`側へ移植する」という方針で進められ、
mping内での検証(pytest・実機ping動作確認)を経て本ライブラリへ移植されたもの
(移植元: `mping/_cli_base.py`, `mping/_logging.py`, `mping/ping/`)。

## 設計方針(iptools)

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

`cli`・`logging`・`ping`はいずれも標準ライブラリのみに依存する自己完結モジュールとして実装しているが、
`ping`パッケージのみOS依存の外部実装を持つ(`ping.windows`はWindows専用の`ctypes`+`iphlpapi.dll`、
`ping.linux`はLinux専用の外部ライブラリ`icmplib`に依存する)。

## モジュール構成

```
src/common/
├── cli.py                # CLI引数解析の共通基盤(BaseArgumentParser, positive_int, non_negative_float)
├── logging.py             # アプリケーション動作ログ構築の共通ヘルパー(build_logger)
├── ftp.py                 # 受信専用の簡易FTPサーバ基盤(SimpleFtpServer, pyftpdlibラッパー。
│                          #   NW機器がバックアップファイルをFTPで"push"してくる方式
│                          #   (例: FortiAnalyzerの`execute backup all-settings ftp ...`)
│                          #   への対応用、2026-09-22追加)
├── ping/                  # ICMP echo (ping) 実行の共通基盤
│   ├── __init__.py          # OS判定によるディスパッチ、ping_async()
│   ├── base.py               # PingResult、ICMP type定数、IP_STATUS→ICMP変換表
│   ├── windows.py             # ctypes + iphlpapi.dll (IcmpSendEcho) 実装 (Windows専用)
│   └── linux.py                # icmplib(ICMPv4Socket)実装。asyncio.to_threadでオフロード
└── iptools/
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

`ping`パッケージが`ping_async()`で内部的にOS判定・ディスパッチまで済ませているのも同じ考え方で、
呼び出し側は宛先IP・TTL・timeout・パケットサイズ・DFフラグを渡すだけでよい。

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

```python
from common.cli import BaseArgumentParser, positive_int

parser = BaseArgumentParser(prog="mytool")
parser.add_argument("--ttl", type=positive_int, default=64)
args = parser.parse_args()
```

```python
from pathlib import Path
from common.logging import build_logger

logger = build_logger("mytool", log_dir=Path.cwd() / "booyaa_log" / "mytool")
logger.warning("何かがおかしい")
```

```python
import asyncio
from common.ping import ping_async

result = asyncio.run(ping_async("8.8.8.8", ttl=64, timeout=1.0, data_size=32, df=False))
if result.ok:
    print(f"RTT={result.rtt*1000:.1f}ms")
else:
    print("NG:", result.icmp_type, result.icmp_code, result.message)
```

```python
from common.ftp import SimpleFtpServer

with SimpleFtpServer(directory="./staging", user="nwadmin", password="P@ssw0rd", port=2121) as server:
    # ここで機器側に、server.portで待受中のFTPサーバへアップロードさせるコマンドを実行する
    received = server.wait_for_file(timeout=1800.0)
    if received is not None:
        print("received:", received.path, received.size, "bytes")
```

## 旧実装からの主な変更点(iptools)

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

## `cli` / `logging` / `ping` 移植時の注意点

- `cli.py`(`common.cli`)・`ping/base.py`・`ping/__init__.py`(`common.ping`)は
  mping内でpytestによる検証済み。`ping/windows.py`は、mpingでの実装時にユーザー環境
  (Windows 11, nitro5-skull)での実機実行(`mping 8.8.8.8`等)によりRTT表示・CSVログ出力とも
  正常動作を確認済みだが、**`common.ping`への移植(import参照先の変更)後の実機再確認はまだ
  行っていない**。`ctypes.WinDLL`をモジュールレベルで参照するため非Windows環境ではimportできず、
  本リポジトリの開発環境(Linux)ではpytestの対象にできない制約も従来通り。

### `ping/linux.py`(2026-09-13、mpingチャットにて実装)

移植時点では`NotImplementedError`を送出するだけのスタブだったが、mping側からの
「Linux版を実装してほしい」という依頼を受け、mpingチャットが直接`common`側を
修正する形で実装した(結果はこの追記として`01_common`へ連携)。

- `icmplib`の**同期API**(`ICMPv4Socket`+`ICMPRequest`)を`asyncio.to_thread`で
  オフロードする構成(Windows実装と対になる「ブロッキング呼び出しをスレッド
  オフロード」パターン)。`icmplib.async_ping`や`icmplib.AsyncSocket`(非同期ソケット)
  ではなく同期APIを選んだ理由は2点: (1) 呼び出し側が1回のpingごとに`PingTarget`の
  状態を更新する設計であること、(2) `AsyncSocket.receive`は`asyncio`の`loop.sock_recv`を
  使う制約上、**実際に応答したホストのアドレス(`reply.source`)を常に`None`にしてしまう**
  (icmplib公式docstringに明記された既知の制約)。TTL超過時に中継ルータのアドレスを
  `reply_from`として取得する必要があるため、同期API側(`ICMPv4Socket.receive`)を採用した。
- 権限: 既定で`privileged=False`(rootを必要としない`SOCK_DGRAM`ベースの非特権ICMP)。
  Windows実装(`iphlpapi.dll`経由、admin権限不要)との体験統一が目的。カーネル側の
  `net.ipv4.ping_group_range`設定次第で非特権ICMPが無効な環境では、ソケット作成が
  `SocketPermissionError`で失敗し、その旨のメッセージを`PingResult.message`に返す
  (呼び出し元でsudo実行または当該sysctl変更を促す)。
- DFフラグ: `icmplib`自体はTTL・TOS(traffic_class)のみをサポートしDFフラグの設定手段を
  持たないため、生ソケット(`ICMPv4Socket.sock`)に対し直接`IP_MTU_DISCOVER`
  (`IP_PMTUDISC_DO`/`IP_PMTUDISC_WANT`)を設定して実現している(`<linux/in.h>`の値を
  直接定義。Python標準の`socket`モジュールには公開されていないため)。
- テスト(`tests/ping/test_linux.py`、9件)は`ICMPv4Socket`を偽の実装に差し替え、
  実ネットワーク・root権限に依存しない形で、成功/タイムアウト/TTL超過/到達不能/
  権限エラー/送信失敗/DFフラグ設定/`asyncio.to_thread`オフロードの各分岐を検証している。
  本リポジトリの開発環境(Linuxコンテナ)でloopback(`127.0.0.1`)への実際のping送受信
  (成功パス・DFフラグ設定含む)による動作確認も別途実施済みだが、**TTL超過・到達不能等の
  実ネットワーク経由での実地確認はまだ行っていない**(開発環境の egress 制限により
  複数ホップ先への到達性テストができないため)。実際のLinux環境での実機確認を推奨する。
- `logging.py`(`common.logging`)の`build_logger`は、移植時点でmping自身はまだ未使用
  (rich画面表示のみで動作ログの出力を必要としていないため)。インターフェースとしては妥当と
  考えられるが、実際の利用シーンでの動作確認はまだ無い。移植にあたり`build_logger`単体の
  基本的な振る舞い(ハンドラ構成・二重登録防止・ファイル出力)を検証するテストを追加した。
- mpingが当初common化候補として挙げていた`fire_and_forget`(`C:\opt\booyaa_old\booyaa\common\fire_and_forget.py`)は、
  mping自身が最終的に`asyncio.TaskGroup`ベースの実装を採用し使用しなくなったため、**今回は
  移植を見送った**。実際に必要とするツールが現れた時点で、そのツールでの利用実績・テストと
  合わせて改めて移植を検討する。

## 開発

```powershell
cd tools/common
uv run pytest
```
