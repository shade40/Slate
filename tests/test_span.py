from __future__ import annotations

import pytest

from slate import Span, color


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
    assert (
        str(Span("hyperlink").as_hyperlink("https://google.com"))
        == "\x1b]8;;https://google.com\x1b\\hyperlink\x1b]8;;\x1b\\"
    )

    assert str(Span("red").as_color("31")) == "\x1b[31mred\x1b[0m"
    assert str(Span("green").as_color("41")) == "\x1b[41mgreen\x1b[0m"

    assert str(
        Span("hello").as_bold().as_underline().as_color("32") == "\x1b[32;1;4mhello"
    )


def test_span_foreground_background_guess():
    assert Span("red").as_color("41") == Span("red", background=color("41"))
    assert Span("green").as_color("32") == Span("green", foreground=color("32"))


def test_span_yield_from():
    def _equals(line: str, expected: list[Span]) -> bool:
        output = [*Span.yield_from(line)]

        if not output == expected:
            print(output)
            return False

        return True

    assert _equals(
        "Test empty",
        [Span("Test empty")],
    )

    assert _equals(
        "\x1b[38;5;141;1;2mTest\x1b",
        [Span("Test", foreground=color("38;5;141"), bold=True, dim=True)],
    )

    assert _equals(
        "\x1b[32mTest",
        [Span("Test", foreground=color("32"))],
    )

    assert _equals(
        "\x1b[96;48;5;230mTest",
        [
            Span(
                "Test",
                foreground=color("96"),
                background=color("48;5;230"),
            )
        ],
    )

    assert _equals(
        "\x1b[92mTest",
        [Span("Test", foreground=color("92"))],
    )

    assert _equals(
        "\x1b[48;2;11;22;33;38;5;230mTest",
        [
            Span(
                "Test",
                background=color("48;2;11;22;33"),
                foreground=color("38;5;230"),
            )
        ],
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
                foreground=color("32"),
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

    assert list(Span("", bold=True).get_characters()) == []


def test_span_hyperlink():
    assert (
        str(Span("Click me", bold=True, hyperlink="https://google.com"))
        == "\x1b]8;;https://google.com\x1b\\\x1b[1mClick me\x1b[0m\x1b]8;;\x1b\\"
    )

    assert (
        str(Span("Click me", hyperlink="https://google.com"))
        == "\x1b]8;;https://google.com\x1b\\Click me\x1b]8;;\x1b\\"
    )


def test_span_length():
    span = Span("Lengthy boye")
    assert (
        len(span)
        == len("Lengthy boye")
        == len(span.as_color("38;5;141").as_hyperlink("https://google.com"))
    )


def test_span_slice():
    span = Span("I am slicable", foreground=color("38;5;141"), bold=True)

    assert span[1:5] == Span(" am ", foreground=color("38;5;141"), bold=True)


def test_span_split():
    span = Span("I must be split", background=color("48;2;11;33;55"))

    assert span.split(" ") == [
        Span("I", background=color("48;2;11;33;55")),
        Span("must", background=color("48;2;11;33;55")),
        Span("be", background=color("48;2;11;33;55")),
        Span("split", background=color("48;2;11;33;55")),
    ]


def test_span_contains():
    span = Span("Some text that contains", bold=True, underline=True)

    assert "text" in span
    assert "Some " in span
    assert "what" not in span
