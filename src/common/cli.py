"""CLI 引数解析の共通基盤.

`argparse.ArgumentParser` に対して、booyaa配下の各CLIツールで共通して
欲しい挙動を追加する薄いラッパー。

- 引数エラー時に usage だけでなく完全な help を表示する
- 数値系引数の共通バリデータ

`tools/mping` で自己完結モジュールとして実装・pytest・実機確認を済ませた上で
本モジュール(`common.cli`)へ移植したもの(移植元: `mping/_cli_base.py`)。
"""

from __future__ import annotations

import argparse
import sys
from typing import NoReturn


class BaseArgumentParser(argparse.ArgumentParser):
    """エラー時に完全なヘルプを表示する `ArgumentParser`.

    標準の `argparse.ArgumentParser.error()` は usage の1行のみを表示して
    終了するが、CLIツールとして不親切なため、full help を表示してから
    終了するように上書きする。
    """

    def error(self, message: str) -> NoReturn:  # noqa: D102 (argparse override)
        self.print_help(sys.stderr)
        sys.stderr.write(f"\n{self.prog}: error: {message}\n")
        raise SystemExit(2)


def positive_int(value: str) -> int:
    """引数バリデーション: 正の整数."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"整数を指定してください: {value!r}") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"正の整数を指定してください: {value!r}")
    return parsed


def non_negative_float(value: str) -> float:
    """引数バリデーション: 0以上の実数."""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"数値を指定してください: {value!r}") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError(f"0以上の数値を指定してください: {value!r}")
    return parsed
