from slate import Screen, Span, color, Color


def test_screen_resize():
    screen = Screen(10, 10)

    screen.write([Span("X")], cursor=(9, 9))

    screen.resize((15, 15))

    assert screen._cells[9][9] == ("X", None, None)

    screen.resize((5, 5))


def test_screen_clear():
    screen = Screen(10, 10)

    screen.clear(fillchar="X")
    print(screen._cells)

    assert all(all(cell == ("X", None, None) for cell in row) for row in screen._cells)


def test_screen_write():
    screen = Screen(10, 10)

    changes = screen.write([Span("X")])
    assert screen.cursor == (1, 0)
    assert changes == 1

    changes = screen.write([Span("Xabc")], cursor=(0, 0))
    assert changes == 3

    changes = screen.write([Span("OOB")], cursor=(10, 10))
    assert changes == 0


def test_screen_opacity():
    screen = Screen(5, 5)

    screen.write(Span("Secret", foreground=color("#ffffff77")))
    screen.cursor = (0, 0)
    screen.write(
        Span(
            " e r t",
            foreground=color("#ffffff22"),
            background=color("#31213477").as_background(),
        )
    )

    print(screen._cells)
    assert screen._cells == [
        [
            (
                "S",
                Color(rgb=(95, 88, 97)),
                Color(rgb=(49, 33, 52), alpha=0.4666666666666667),
            ),
            (
                "e",
                Color(rgb=(76, 62, 79)),
                Color(rgb=(49, 33, 52), alpha=0.4666666666666667),
            ),
            (
                "c",
                Color(rgb=(95, 88, 97)),
                Color(rgb=(49, 33, 52), alpha=0.4666666666666667),
            ),
            (
                "r",
                Color(rgb=(76, 62, 79)),
                Color(rgb=(49, 33, 52), alpha=0.4666666666666667),
            ),
            (
                "e",
                Color(rgb=(95, 88, 97)),
                Color(rgb=(49, 33, 52), alpha=0.4666666666666667),
            ),
        ],
        [
            (
                "t",
                Color(rgb=(76, 62, 79)),
                Color(rgb=(49, 33, 52), alpha=0.4666666666666667),
            ),
            (" ", None, None),
            (" ", None, None),
            (" ", None, None),
            (" ", None, None),
        ],
        [
            (" ", None, None),
            (" ", None, None),
            (" ", None, None),
            (" ", None, None),
            (" ", None, None),
        ],
        [
            (" ", None, None),
            (" ", None, None),
            (" ", None, None),
            (" ", None, None),
            (" ", None, None),
        ],
        [
            (" ", None, None),
            (" ", None, None),
            (" ", None, None),
            (" ", None, None),
            (" ", None, None),
        ],
    ]


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
