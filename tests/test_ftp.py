"""SimpleFtpServer(common.ftp)の単体テスト。

実際にpyftpdlibのサーバをlocalhost上に(port=0でOS自動割当のポートに)起動し、
標準ライブラリの`ftplib.FTP`クライアントで実際にファイルをアップロードすることで、
プロトコルレベルの動作(ログイン認証・STORコマンド・受動モードでのデータ転送)を
検証する(モックではなく実際のTCP通信を行う統合テストに近い形。`common.ftp`自体が
「FTPプロトコルの実装を薄くラップするだけ」のモジュールであり、モックしても
ラップの薄さゆえ検証価値が薄いため)。
"""
from __future__ import annotations

import ftplib
import io
import logging
from pathlib import Path

import pytest

from common.ftp import DEFAULT_PORT, SimpleFtpServer


@pytest.fixture
def ftp_server(tmp_path):
    server = SimpleFtpServer(directory=tmp_path, user='testuser', password='testpass', port=0)
    server.start()
    yield server
    server.stop()


def test_port_zero_gets_os_assigned_port(tmp_path):
    server = SimpleFtpServer(directory=tmp_path, user='u', password='p', port=0)
    try:
        assert server.port != 0
        assert server.port > 0
    finally:
        server.stop()


def test_default_port_constant_is_non_privileged():
    assert DEFAULT_PORT == 2121


def test_directory_is_created_if_missing(tmp_path):
    target = tmp_path / 'nested' / 'staging'
    assert not target.exists()
    server = SimpleFtpServer(directory=target, user='u', password='p', port=0)
    try:
        assert target.is_dir()
    finally:
        server.stop()


def test_upload_via_real_ftp_client_is_recorded(ftp_server, tmp_path):
    content = b'hello from a fake FortiAnalyzer backup\n' * 100

    ftp = ftplib.FTP()
    ftp.connect('127.0.0.1', ftp_server.port, timeout=10)
    ftp.login('testuser', 'testpass')
    ftp.storbinary('STOR backup.dat', io.BytesIO(content))
    ftp.quit()

    received = ftp_server.wait_for_file(timeout=10)
    assert received is not None
    assert received.filename == 'backup.dat'
    assert received.size == len(content)
    assert received.path.read_bytes() == content
    assert received.path.parent == tmp_path


def test_upload_with_wrong_credentials_is_rejected(ftp_server):
    ftp = ftplib.FTP()
    ftp.connect('127.0.0.1', ftp_server.port, timeout=10)
    with pytest.raises(ftplib.error_perm):
        ftp.login('testuser', 'wrongpass')
    ftp.close()

    assert ftp_server.received == []


def test_wait_for_file_times_out_when_nothing_uploaded(ftp_server):
    received = ftp_server.wait_for_file(timeout=0.3, poll_interval=0.05)
    assert received is None


def test_context_manager_starts_and_stops(tmp_path):
    with SimpleFtpServer(directory=tmp_path, user='u', password='p', port=0) as server:
        assert server._thread is not None
        ftp = ftplib.FTP()
        ftp.connect('127.0.0.1', server.port, timeout=10)
        ftp.login('u', 'p')
        ftp.quit()
    assert server._thread is None


def test_pyftpdlib_logger_preconfigured_to_prevent_info_spam():
    """実機で発覚した不具合(2026-09-23)の回帰テスト: pyftpdlibは`serve_forever()`内で
    `pyftpdlib`ロガーにハンドラが無いと判断すると、自前で`config_logging()`を呼んで
    levelをINFOにリセットしてしまう(`pyftpdlib.log._log_start()`参照)。`common.ftp`が
    import時点で先にハンドラを追加しておくことでこれを防いでいることを確認する
    (`common/ftp.py`のモジュールdocstring直下のコメント参照)。"""
    logger = logging.getLogger('pyftpdlib')
    assert logger.handlers, 'ハンドラが無いとpyftpdlibが自前でconfig_logging()を呼びlevelを上書きしてしまう'
    assert logger.level == logging.WARNING
    assert logger.propagate is False


def test_starting_server_does_not_print_info_level_noise(capsys, tmp_path):
    """実際にサーバを起動・停止しても、`concurrency model: async`等のpyftpdlib自身の
    INFOログが標準エラー出力(画面)に出ないことの回帰テスト(2026-09-23、実機で
    こうぢさんが発見)。"""
    server = SimpleFtpServer(directory=tmp_path, user='u', password='p', port=0)
    server.start()
    server.stop()

    captured = capsys.readouterr()
    assert 'concurrency model' not in captured.err
    assert 'concurrency model' not in captured.out
    assert 'starting FTP server' not in captured.err
    assert 'starting FTP server' not in captured.out


def test_multiple_uploads_are_all_recorded(ftp_server):
    for i in range(3):
        ftp = ftplib.FTP()
        ftp.connect('127.0.0.1', ftp_server.port, timeout=10)
        ftp.login('testuser', 'testpass')
        ftp.storbinary(f'STOR file{i}.dat', io.BytesIO(f'data{i}'.encode()))
        ftp.quit()

    received = ftp_server.wait_for_file(timeout=10)
    assert received is not None
    assert len(ftp_server.received) == 3
    names = {r.filename for r in ftp_server.received}
    assert names == {'file0.dat', 'file1.dat', 'file2.dat'}
