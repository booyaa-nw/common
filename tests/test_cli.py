import argparse

import pytest

from common.cli import BaseArgumentParser, non_negative_float, positive_int


def test_positive_int_accepts_positive_values():
    assert positive_int("5") == 5


def test_positive_int_rejects_zero_and_negative():
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("0")
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("-1")


def test_positive_int_rejects_non_numeric():
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("abc")


def test_non_negative_float_accepts_zero():
    assert non_negative_float("0") == 0.0
    assert non_negative_float("1.5") == 1.5


def test_non_negative_float_rejects_negative():
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_float("-0.1")


def test_base_argument_parser_error_exits_with_code_2(capsys):
    parser = BaseArgumentParser(prog="test")
    parser.add_argument("--ttl", type=positive_int)
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--ttl", "-1"])
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "usage" in captured.err.lower()
