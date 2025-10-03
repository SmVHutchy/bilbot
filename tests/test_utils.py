import pytest

from bot import clamp_text


def test_clamp_text_none():
    assert clamp_text(None, 10) == ""


def test_clamp_text_short():
    assert clamp_text("Hallo", 10) == "Hallo"


def test_clamp_text_long_truncates_with_ellipsis():
    text = "x" * 20
    result = clamp_text(text, 10)
    assert result == ("x" * 9) + "…"  # max_len=10 -> 9 chars + ellipsis


def test_clamp_text_non_string():
    # len(123) wirft Exception -> Fallback ohne Ellipse
    assert clamp_text(123, 2) == "12"
