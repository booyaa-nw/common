"""アプリケーション動作ログの共通基盤.

ping結果CSV等、ツールが本来の目的で出力するデータログとは別に、ツール自体の
動作ログ(エラー・警告など)を出力するための最小限のロガー設定ヘルパー。

`tools/mping` で自己完結モジュールとして実装した上で本モジュール
(`common.logging`)へ移植したもの(移植元: `mping/_logging.py`)。

移植時点でmping自身はこのモジュールを未使用(rich画面表示のみで動作ログの
出力を必要としていないため)。インターフェースの形は妥当と考えられるが、
実際の利用シーンでの動作確認はまだ無い。移植にあたり、`build_logger`単体の
基本的な振る舞い(ハンドラ構成・二重登録防止・ファイル出力)を検証する
テストを追加した。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def build_logger(
    name: str,
    *,
    log_dir: Path | None = None,
    level: int = logging.INFO,
    filename: str = "app.log",
) -> logging.Logger:
    """名前付きロガーを構築する.

    `log_dir` を指定した場合はファイル出力ハンドラを追加する(ディレクトリが
    存在しない場合は作成する)。標準エラー出力へのハンドラは常に追加する。
    同じ`name`で再度呼び出した場合、ハンドラの二重登録は行わない
    (既にハンドラが登録済みのロガーをそのまま返す)。
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        # 二重登録防止 (再呼び出し時)
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / filename, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
