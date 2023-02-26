import os
import sys
import tempfile
from io import StringIO

from undertone.core import ColorSpace, get_color_space, parse_mouse_event


def test_get_color_space():
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


def test_parse_mouse_event():
    assert parse_mouse_event("\x1b") == parse_mouse_event("\x1b[1;2m") == None

    assert parse_mouse_event("\x1b[<0;12;23M") == "mouse:left-click@12;23"
    assert parse_mouse_event("\x1b[<2;45;8m") == "mouse:right-release@45;8"
