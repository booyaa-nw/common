import logging

from common.logging import build_logger


def test_build_logger_sets_name_and_level():
    logger = build_logger("common.test.basic", level=logging.WARNING)
    assert logger.name == "common.test.basic"
    assert logger.level == logging.WARNING
    assert logger.propagate is False


def test_build_logger_always_adds_stream_handler():
    logger = build_logger("common.test.stream")
    assert any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in logger.handlers)


def test_build_logger_without_log_dir_has_no_file_handler():
    logger = build_logger("common.test.nofile")
    assert not any(isinstance(h, logging.FileHandler) for h in logger.handlers)


def test_build_logger_second_call_does_not_duplicate_handlers():
    first = build_logger("common.test.dup")
    handler_count = len(first.handlers)
    second = build_logger("common.test.dup")
    assert first is second
    assert len(second.handlers) == handler_count


def test_build_logger_with_log_dir_creates_file_and_writes(tmp_path):
    log_dir = tmp_path / "logs"
    logger = build_logger("common.test.file", log_dir=log_dir, filename="app.log")

    assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)

    log_path = log_dir / "app.log"
    assert log_path.exists()

    logger.info("hello")
    for handler in logger.handlers:
        handler.flush()
    content = log_path.read_text(encoding="utf-8")
    assert "hello" in content
    assert "[INFO] common.test.file" in content


def test_build_logger_creates_log_dir_if_missing(tmp_path):
    log_dir = tmp_path / "does_not_exist_yet" / "nested"
    build_logger("common.test.mkdir", log_dir=log_dir)
    assert log_dir.is_dir()
