"""シンプルな受信専用FTPサーバの共通実装。

NW機器(FortiAnalyzer等)がバックアップファイルをFTPで"push"してくる形式
(`execute backup all-settings ftp <server> ...`等)に対応するため、booyaa側で
一時的にFTPサーバを立てて受信する用途を想定した軽量なラッパー。特定のベンダー・
特定のツールに依存しない汎用ユーティリティのため(`architecture/plugin-architecture-consideration.md`
の「`common`の扱いについて」参照)、`net_config`/`config_backup`側ではなく
`common`側に実装する(こうぢさん指定)。

プロトコル実装自体は自前で書かず、`pyftpdlib`(pure Python、能動/受動モード双方に
対応した成熟したFTPサーバライブラリ)に委譲する。FTPプロトコルは受動モード(PASV)の
ポートネゴシエーション等、自前実装だと事故りやすい仕様を多く含む一方、`pyftpdlib`は
2.x系で`asyncore`/`asynchat`(Python 3.12で標準ライブラリから削除)への依存を廃し、
独自実装(`pyftpdlib.ioloop`)に置き換えているため、本プロジェクトが使う新しいPython
(3.14系)でも問題なく動作する(2026-09-22、クラウド側サンドボックスで確認済み)。

本モジュールは「一時ディレクトリへの書き込み専用アカウントを1つ登録し、
バックグラウンドスレッドで起動・停止できる」という薄いラッパーのみを提供する。

## ポート番号について

`SimpleFtpServer`はデフォルトで非特権ポート`DEFAULT_PORT`(2121番)を使う。FTPの
標準ポート21番はLinux/一部環境で特権(root権限)が無いとbindできない上、ホスト側で
既に何らかのFTPサービスが動いている可能性もあるため、既定は21番を避けている。
呼び出し側(例: `config_backup.faz`)が`port`引数で変更可能にすること
(「ftpサーバのポート番号はオプションで変更可能としてください」というこうぢさんの
要望に対応)。

機器側のコマンド(例: FortiAnalyzerの`execute backup all-settings ftp <addr> ...`)で
21番以外のポートを指定する場合は、`<FTPサーバIPアドレス>:<ポート番号>`という形式で
アドレスを渡す(コマンド側の仕様。本サーバはどのポートでlistenしていても、
呼び出し側がその情報を使ってこの形式のアドレス文字列を組み立てる)。
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

# pyftpdlib自身の接続ごとの詳細ログ(既定でINFO)が画面を汚すため、WARNING以上に絞る。
#
# ## 不具合と修正(2026-09-23、実機で発覚)
#
# 単に`setLevel(logging.WARNING)`するだけでは不十分だった。pyftpdlibの
# `FTPServer._log_start()`(`serve_forever()`から呼ばれる、バックグラウンドスレッド側)は、
# `pyftpdlib.log.is_logging_configured()`(`pyftpdlib`ロガーにハンドラが1つも
# 無く、かつルートロガーにもハンドラが無ければFalseを返す)がFalseの場合、
# 「ユーザーがロガーを設定していない」と判断して`config_logging()`を**自前で**
# 呼んでしまう。`config_logging()`は既定levelが`logging.INFO`の
# `StreamHandler`(stderr)を新規に追加して`pyftpdlib`ロガーへ`addHandler()`+
# `setLevel(logging.INFO)`するため、本モジュールimport時に設定した
# `setLevel(logging.WARNING)`が実行時(サーバ起動時)に**上書きされてしまい**、
# `concurrency model: async`/`FTP session opened`/`USER ... logged in`/
# `STOR ... completed=...`等のINFOログが画面(標準エラー出力)にそのまま
# 出力されてしまっていた(実機テストでこうぢさんが発見)。
#
# 対策: `pyftpdlib`ロガーに**こちら側で先にハンドラを追加**しておくことで
# `is_logging_configured()`をTrueにし、pyftpdlib自身の`config_logging()`呼び出し
# (＝level上書き)を未然に防ぐ。`propagate = False`も併せて設定し、ルートロガー側に
# ハンドラが追加された場合(将来アプリ全体でlogging.basicConfig()する等)でも
# 二重出力・意図しない伝播が起きないようにする。これにより、WARNING未満(INFO/DEBUG)
# は握りつぶされ、WARNING以上(実際のエラー等、調査に必要な情報)のみ`StreamHandler`
# 経由で表示される、という当初の意図通りの挙動になる。
#
# アプリケーション側で調査目的に詳細ログを見たい場合は、本モジュールimport後に
# 個別に`logging.getLogger('pyftpdlib').setLevel(...)`を上書きすればよい
# (ハンドラは既に設定済みのため、レベルを下げるだけで詳細ログが見えるようになる)。
_pyftpdlib_logger = logging.getLogger('pyftpdlib')
_pyftpdlib_logger.setLevel(logging.WARNING)
_pyftpdlib_logger.addHandler(logging.StreamHandler())
_pyftpdlib_logger.propagate = False

# 21番(FTP標準ポート)は特権ポートのため既定では避ける。
DEFAULT_PORT = 2121

# 受動モード(PASV)用のポート範囲。ファイアウォール越しにレンジを絞りたい場合は
# `SimpleFtpServer(..., passive_ports=(start, end))`で上書きする。
DEFAULT_PASSIVE_PORTS = (60000, 60100)


@dataclass
class ReceivedFile:
    """アップロードされたファイル1件分の記録。"""
    filename: str
    path: Path
    size: int


class SimpleFtpServer:
    """一時的な受信専用FTPサーバ。`with`文、または`start()`/`stop()`で使う。

    Args:
        directory: アップロードされたファイルを書き込むディレクトリ(存在しなければ作成する)。
        user: FTPログインユーザー名。
        password: FTPログインパスワード。
        host: bindするアドレス(既定"0.0.0.0"、全インタフェースでlisten)。
        port: listenするポート(既定`DEFAULT_PORT`=2121)。`0`を指定するとOSが空きポートを
            自動割り当てする(テスト用途向け)。実際にbindされたポート番号は、
            インスタンス生成後`self.port`で取得できる(コンストラクタ内でbind自体は
            完了しているため、`start()`前でも参照可能)。
        passive_ports: 受動モード(PASV)用のポート範囲(既定`DEFAULT_PASSIVE_PORTS`)。
    """

    def __init__(self, directory: str | Path, user: str, password: str,
                 host: str = '0.0.0.0', port: int = DEFAULT_PORT,
                 passive_ports: tuple[int, int] = DEFAULT_PASSIVE_PORTS):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.host = host

        self.received: list[ReceivedFile] = []
        self._lock = threading.Lock()

        authorizer = DummyAuthorizer()
        authorizer.add_user(user, password, str(self.directory), perm='elradfmwMT')

        handler_cls = _make_handler_class(
            authorizer=authorizer,
            passive_ports=range(passive_ports[0], passive_ports[1] + 1),
            on_file_received=self._record_received,
        )

        # FTPServer()のコンストラクタ内でbind/listenまで完了する(pyftpdlibの
        # Acceptor.__init__())。port=0(OS自動割り当て)を指定した場合も、
        # ここで実際に割り当てられた番号が確定するため、start()を呼ぶ前から
        # self.portで参照できる。
        self._server = FTPServer((host, port), handler_cls)
        self.port: int = self._server.socket.getsockname()[1]

        self._thread: Optional[threading.Thread] = None

    def _record_received(self, file_path: str) -> None:
        path = Path(file_path)
        with self._lock:
            self.received.append(ReceivedFile(filename=path.name, path=path, size=path.stat().st_size))

    def start(self) -> None:
        """バックグラウンドスレッドでサーバを起動する(既に起動済みなら何もしない)。"""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """サーバを停止する(未起動なら何もしない)。"""
        if self._thread is None:
            return
        self._server.close_all()
        self._thread.join(timeout=timeout)
        self._thread = None

    def wait_for_file(self, timeout: float = 60.0, poll_interval: float = 0.5) -> Optional[ReceivedFile]:
        """最初にアップロードされたファイルを待つ(ポーリング)。

        機器側のFTPアップロードは`SimpleFtpServer`とは別スレッド(サーバの
        イベントループ)で非同期に処理されるため、呼び出し側(機器へコマンドを
        送ってその完了を待っている側)がファイルの到着を確認したい場合はこれを使う。
        取得できなければ(タイムアウトするまでに1件もアップロードが無ければ)`None`を返す。
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self.received:
                    return self.received[0]
            time.sleep(poll_interval)
        with self._lock:
            return self.received[0] if self.received else None

    def __enter__(self) -> 'SimpleFtpServer':
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


def _make_handler_class(authorizer: DummyAuthorizer, passive_ports: range,
                         on_file_received: Callable[[str], None]) -> type:
    """`SimpleFtpServer`インスタンスごとに独立した`FTPHandler`サブクラスを作る。

    pyftpdlibは`FTPServer(address, handler_cls)`のように**クラス自体**を渡す設計
    (接続ごとにpyftpdlib側が`handler_cls(conn, server)`でインスタンス化する)のため、
    `authorizer`等のインスタンス固有の設定はクラス変数として持たせる必要がある。
    `SimpleFtpServer`を複数同時に使うケース(将来、複数機器を並列でバックアップする
    ような場合)に備え、`type()`で都度専用のサブクラスを生成して設定を分離している
    (クラス変数をグローバルに共有しない)。
    """

    class _Handler(FTPHandler):
        pass

    _Handler.authorizer = authorizer
    _Handler.passive_ports = passive_ports

    def _on_file_received(self, file_path):  # noqa: ANN001 - pyftpdlibのフック名を踏襲
        on_file_received(file_path)

    _Handler.on_file_received = _on_file_received

    return _Handler
