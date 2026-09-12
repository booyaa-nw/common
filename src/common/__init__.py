"""common: booyaa配下の各ツールから使う共通ライブラリ.

- `common.iptools` : IPアドレス計算・ネットワーク情報取得。
- `common.cli` : CLI引数解析の共通基盤(`BaseArgumentParser`、数値バリデータ)。
- `common.logging` : アプリケーション動作ログ構築の共通ヘルパー(`build_logger`)。
- `common.ping` : ICMP echo (ping) 実行の共通基盤(OS判定ディスパッチ、結果モデル)。
"""

__version__ = "0.1.0"
