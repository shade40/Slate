from io import StringIO

from undertone import Terminal


def get_clean_terminal_object() -> Terminal:
    stream = StringIO()

    return Terminal(stream=stream)


def test_foreground_color():
    assert len(Terminal().get_fg_color()) == 6
