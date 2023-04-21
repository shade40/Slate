from io import StringIO

from slate import ColorSpace, Span, Terminal


def test_terminal_color_space_forcing():
    term = Terminal()

    original_space = term.color_space
    term.color_space = ColorSpace.EIGHT_BIT

    assert term.color_space != original_space


def test_terminal_colors_match_length():
    assert len(Terminal().get_fg_color()) == len(Terminal().get_bg_color()) == 6


def test_terminal_clear():
    term = Terminal()

    term.write("X", cursor=(0, 0))
    term.clear(fillchar="O")
    assert term._screen._cells[0][0] == "O"


def test_terminal_write_control():
    stream = StringIO()

    term = Terminal(stream=stream)

    # StringIO doesn't support flushing, so we can't test it. It _should_ work though!
    term.write_control("\x1b[H")
    assert stream.getvalue() == "\x1b[H"


def test_terminal_draw():
    # We construct the terminal with a throwaway stream, so we can get the inital redraw
    # out before testing for our expected output.
    term = Terminal(stream=StringIO())
    term.clear("X")
    term.draw()

    term.stream = stream = StringIO()
    term.write("I am terminal", force_overwrite=True)

    print(term._screen._change_buffer.gather())
    term.draw()
    print(term._screen._change_buffer.gather())
    assert stream.getvalue() == "\x1b[1;1HI am terminal\x1b[0m", repr(stream.getvalue())


def test_terminal_size():
    term = Terminal()

    term._previous_size = (0, 0)
    assert term.size == (term.width, term.height)


def test_terminal_cursor():
    term = Terminal()

    assert term.cursor == (0, 0)

    term.write("1234")
    assert term.cursor == (4, 0)

    term.cursor = (1, 1)
    assert term.cursor == (1, 1)


def test_terminal_write_diff_types():
    term = Terminal()

    term._screen.render()
    term.write("\x1b[38;5;141;1;2mHello")

    assert term._screen._cells[0][0:5] == [
        "\x1b[38;5;141;1;2mH",
        "\x1b[38;5;141;1;2me",
        "\x1b[38;5;141;1;2ml",
        "\x1b[38;5;141;1;2ml",
        "\x1b[38;5;141;1;2mo\x1b[0m",
    ]

    changes = term.write(
        [Span("Yellow", foreground="38;5;141", bold=True, dim=True)], cursor=(0, 0)
    )

    # 3 changes:
    # - "H"        -> "Y"
    # - "o\x1b[0m" -> "o"
    # - " "        -> "w"
    assert changes == 3
