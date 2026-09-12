"""iptools全体で使う共通の戻り値型.

このライブラリの全ての公開関数は、例外を送出する代わりに `IPToolsResult` を返す。

- `ok=True` のときだけ `value` に意味がある。
- `ok=False` のときだけ `reason` / `message` に意味がある。
- 想定外の例外も各公開関数の境界(`@safe_call`)で捕捉して `Reason.UNEXPECTED_ERROR` に変換するため、
  呼び出し側は基本的に try/except を書かずに `result.ok` だけを見ればよい。

なお「判定の答えそのものがtrue/falseである関数」(is_my_nic_addrなど)では、
`value` に生のbool値を直接入れない。`ok=True, value=False` という形は
「ok」という言葉の直感（"そのまま使ってよい"）と紛れやすいためで、
かわりに意味の分かる名前を持つ小さなdataclassに包んで返す
(例: `value.is_mine` のように、fieldを読まないと答えが分からない形にする)。
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Reason(Enum):
    """`ok=False` のときの失敗理由."""

    MISSING_PREFIX = auto()  # "/"によるprefix(CIDR/マスク)指定が無い
    INVALID_ADDRESS = auto()  # アドレス部分の形式が不正
    INVALID_PREFIX = auto()  # CIDR/ネットマスク部分の形式が不正
    INVALID_FQDN = auto()  # FQDN/ホスト名の形式が不正
    NOT_RESOLVABLE = auto()  # 名前解決できない
    NOT_MY_ADDRESS = auto()  # 自ホストに割り当てられたアドレスではない
    NO_ROUTE = auto()  # 宛先に対する送信元/経路が決定できない
    UNEXPECTED_ERROR = auto()  # 想定外の例外(messageに詳細を格納する)


@dataclass(frozen=True)
class IPToolsResult(Generic[T]):
    """iptools の全公開関数が返す統一戻り値.

    Attributes:
        ok: 計算・判定を実行できたか。Trueのときだけ`value`が意味を持つ。
        value: 実行できた場合の結果。`ok=False`のときは常にNone。
        reason: 実行できなかった理由。`ok=True`のときは常にNone。
        message: 人間向けの詳細メッセージ。`ok=True`のときは常にNone。
    """

    ok: bool
    value: T | None
    reason: Reason | None
    message: str | None

    @classmethod
    def success(cls, value: T) -> "IPToolsResult[T]":
        return cls(ok=True, value=value, reason=None, message=None)

    @classmethod
    def failure(cls, reason: Reason, message: str) -> "IPToolsResult[T]":
        return cls(ok=False, value=None, reason=reason, message=message)


def safe_call(func: Callable[..., "IPToolsResult"]) -> Callable[..., "IPToolsResult"]:
    """公開関数の境界で想定外の例外を捕捉し、`Reason.UNEXPECTED_ERROR` に変換するデコレータ.

    意図的に `IPToolsResult.failure(...)` をreturnしている箇所はそのまま透過する。
    ここで捕まえるのは「バグ、あるいは想定していなかった環境要因」による例外のみ。
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # 最終防衛ライン。ここより上には例外を漏らさない。
            return IPToolsResult.failure(
                Reason.UNEXPECTED_ERROR,
                f"{type(exc).__name__}: {exc}",
            )

    return wrapper
