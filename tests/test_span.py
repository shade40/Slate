import pytest

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


def test_span_yield_from():
    def _equals(line: str, expected: list[Span]) -> bool:
        return list(Span.yield_from(line)) == expected

    assert _equals(
        "\x1b[38;5;141;1;2mTest\x1b",
        [Span("Test", foreground="38;5;141", bold=True, dim=True)],
    )

    assert _equals(
        "\x1b[32mTest",
        [Span("Test", foreground="32")],
    )

    assert _equals(
        "\x1b[96;48;5;230mTest",
        [Span("Test", foreground="96", background="48;5;230")],
    )

    assert _equals(
        "\x1b[92mTest",
        [Span("Test", foreground="92")],
    )

    assert _equals(
        "\x1b[48;2;11;22;33;38;5;230mTest",
        [Span("Test", background="48;2;11;22;33", foreground="38;5;230")],
    )

    assert _equals(
        "\x1b[1;2;3;4;32mTest\x1b[22;39mnot bold not colored",
        [
            Span(
                "Test",
                bold=True,
                dim=True,
                italic=True,
                underline=True,
                foreground="32",
            ),
            Span("not bold not colored", italic=True, underline=True),
        ],
    )

    assert _equals(
        "\x1b[3;1mItalic-bold\x1b[22;23mNo longer",
        [
            Span("Italic-bold", italic=True, bold=True),
            Span("No longer"),
        ],
    )

    with pytest.raises(ValueError):
        list(Span.yield_from("\x1b[615mThis won't parse"))

    list(Span.yield_from("\x1b[38;8;11mWhat is this?"))


def test_span_get_characters():
    span = Span("Test", bold=True, italic=True)

    assert list(span.get_characters()) == [
        "\x1b[1;3mT",
        "e",
        "s",
        "t\x1b[0m",
    ]

    assert list(span.mutate(reset_after=False).get_characters()) == [
        "\x1b[1;3mT",
        "e",
        "s",
        "t",
    ]

    assert list(span.get_characters(always_include_sequence=True)) == [
        "\x1b[1;3mT",
        "\x1b[1;3me",
        "\x1b[1;3ms",
        "\x1b[1;3mt\x1b[0m",
    ]
