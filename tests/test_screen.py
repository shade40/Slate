from slate import Screen, Span


def test_screen_resize():
    screen = Screen(10, 10)

    screen.write([Span("X")], cursor=(9, 9))

    screen.resize((15, 15))

    assert screen._cells[9][9] == "X"

    screen.resize((5, 5))


def test_screen_clear():
    screen = Screen(10, 10)

    screen.clear(fillchar="X")
    print(screen._cells)

    assert all(all(cell == "X" for cell in row) for row in screen._cells)


def test_screen_write():
    screen = Screen(10, 10)

    changes = screen.write([Span("X")])
    assert screen.cursor == (1, 0)
    assert changes == 1

    changes = screen.write([Span("Xabc")], cursor=(0, 0))
    assert changes == 3

    changes = screen.write([Span("OOB")], cursor=(10, 10))
    assert changes == 0


def test_screen_render():
    screen = Screen(5, 5, fillchar="X")

    assert (output := screen.render()) == (
        "\x1b[0;0HXXXXX"
        + "\x1b[1;0HXXXXX"
        + "\x1b[2;0HXXXXX"
        + "\x1b[3;0HXXXXX"
        + "\x1b[4;0HXXXXX\x1b[0m"
    )

    screen.write([Span("X", bold=True)], cursor=(4, 4))

    assert screen.render() == "\x1b[4;4H\x1b[1mX\x1b[0m"

    output = screen.render(origin=(1, 1), redraw=True)

    assert output == (
        "\x1b[1;1HXXXXX"
        + "\x1b[2;1HXXXXX"
        + "\x1b[3;1HXXXXX"
        + "\x1b[4;1HXXXXX"
        + "\x1b[5;1HXXXX\x1b[1mX\x1b[0m"
    ), repr(output)
