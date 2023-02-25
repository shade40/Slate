from undertone import Span


def test_span_creation():
    assert str(
        Span("hello", bold=True, italic=True, reset_after=False) == "\x1b[1;3mhello"
    )


def test_span_mutation():
    assert str(Span("bold").as_bold()) == "\x1b[1mbold\x1b[0m"
    assert str(Span("dim").as_dim()) == "\x1b[2mdim\x1b[0m"
    assert str(Span("italic").as_italic()) == "\x1b[3mitalic\x1b[0m"
    assert str(Span("underline").as_underline()) == "\x1b[4munderline\x1b[0m"
    assert str(Span("blink").as_blink()) == "\x1b[5mblink\x1b[0m"
    assert str(Span("fast_blink").as_fast_blink()) == "\x1b[6mfast_blink\x1b[0m"
    assert str(Span("invert").as_invert()) == "\x1b[7minvert\x1b[0m"
    assert str(Span("conceal").as_conceal()) == "\x1b[8mconceal\x1b[0m"
    assert str(Span("strike").as_strike()) == "\x1b[9mstrike\x1b[0m"

    assert str(Span("red").as_color("31")) == "\x1b[31mred\x1b[0m"
    assert str(Span("green").as_color("41")) == "\x1b[41mgreen\x1b[0m"

    assert str(
        Span("hello").as_bold().as_underline().as_color("32") == "\x1b[32;1;4mhello"
    )


def test_span_foreground_background_guess():
    assert Span("red").as_color("41") == Span("red", background="41")
    assert Span("green").as_color("32") == Span("green", foreground="32")
