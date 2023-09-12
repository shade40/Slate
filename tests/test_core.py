import os
import sys
import tempfile
from io import StringIO

from slate.core import ColorSpace, get_color_space, parse_mouse_event, width
from slate.color import Color
from slate.span import Span


def test_core_get_color_space():
    os.environ["NO_COLOR"] = "1"
    assert get_color_space() == ColorSpace.NO_COLOR
    del os.environ["NO_COLOR"]
    os.environ["COLORTERM"] = ""

    os.environ["TERM"] = "xterm-256color"
    assert get_color_space() == ColorSpace.EIGHT_BIT

    os.environ["COLORTERM"] = "truecolor"
    os.environ["TERM"] = "xterm"
    assert get_color_space() == ColorSpace.TRUE_COLOR

    os.environ["COLORTERM"] = ""
    os.environ["TERM"] = ""
    assert get_color_space() == ColorSpace.STANDARD


def test_core_parse_mouse_event():
    assert parse_mouse_event("\x1b") == parse_mouse_event("\x1b[1;2m") == None

    assert parse_mouse_event("\x1b[<0;12;23M") == "mouse:left_click@12;23"
    assert parse_mouse_event("\x1b[<2;45;8m") == "mouse:right_release@45;8"


def test_core_width():
    assert width("Test") == 4

    assert width(
        Span("Other test", foreground=Color.from_ansi("38;5;141"), bold=True)
    ) == len("Other test")
    assert width("\x1b[38;5;141;1;2;3;4mBig test") == len("Big test")
