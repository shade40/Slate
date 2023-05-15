"""The Span class, a piece of formatted text for the terminal."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from itertools import chain
from typing import Any, Generator, Iterable
from html import escape

from .color import Color

SETTERS = {
    "bold": "1",
    "dim": "2",
    "italic": "3",
    "underline": "4",
    "blink": "5",
    "fast_blink": "6",
    "invert": "7",
    "conceal": "8",
    "strike": "9",
}

SETTERS_TO_STYLES = {value: key for key, value in SETTERS.items()}

UNSETTERS = {
    "dim": "22",
    "bold": "22",
    "italic": "23",
    "underline": "24",
    "blink": "25",
    "blink2": "26",
    "invert": "27",
    "invisible": "28",
    "strikethrough": "29",
    "foreground": "39",
    "background": "49",
    "overline": "54",
}

UNSETTERS_TO_STYLES = {value: key for key, value in UNSETTERS.items()}

RE_ANSI_STYLES = re.compile(r"\x1b\[(?:(.*?))[mH]([^\x1b]+)(?=\x1b)")

SVG_CHAR_WIDTH = 0.60167
SVG_CHAR_HEIGHT = 1.265
SVG_RECT_WIDTH = SVG_CHAR_WIDTH * 1.1
SVG_RECT_HEIGHT = SVG_CHAR_HEIGHT * 1.08

# We manually set all text to have an alignment-baseline of
# text-after-edge to avoid block characters rendering in the
# wrong place (not at the top of their "box"), but with that
# our background rects will be rendered in the wrong place too,
# so this is used to offset that.
SVG_RECT_BASELINE_OFFSET = 0.17

STYLE_TO_CSS = {
    "bold": ("font-weight", "bold"),
    "italic": ("font-style", "italic"),
    "dim": ("opacity", "0.7"),
    "underline": ("text-decoration", "underline"),
    "strikethrough": ("text-decoration", "line-through"),
    "overline": ("text-decoration", "overline"),
}


def _escape_html(text: str) -> str:
    """Escapes HTML and replaces ' ' with &nbsp;."""

    return escape(text).replace(" ", "&#160;")


def _is_block(text: str) -> bool:
    """Determines whether the given text only contains block characters.

    These characters reside in the unicode range of 9600-9631, which is what we test
    against.
    """

    return all(9600 <= ord(char) <= 9631 for char in text)


def _is_background_color(body: str) -> bool:
    """Determines whether the given color body is a background.

    This assumes that the given body is already color.
    """

    return body.startswith("4") or (body.startswith("10") and len(body) > 2)


def _is_valid_color(body: str) -> bool:
    """Determines whether the given sequence body is a valid color.

    It recognizes the following:

    - Standard colors in ranges (30, 38), (40, 48), (90, 97), (100, 107), not
        including the endpoint
    - RGB colors (`38;2;xxx` or `48;2;xxx`)
    - 8-bit colors (`38;5;xxx` or `48;5;xxx`)
    """

    if body.isdigit():
        index = int(body)

        if 30 <= index <= 49 and index not in [38, 48]:
            return True

        if 90 <= index <= 97 or 100 <= index <= 107:
            return True

        return False

    # Body will always start with 38 or 48, since it is guaranteed by the caller
    parts = body.split(";")

    if parts[1] == "2":
        return len(parts) == 5

    if parts[1] == "5":
        return len(parts) == 3

    return False


def _parse_sequence(seq: str, options: dict[str, bool | str]) -> None | str:
    """Parses the given sequence into an option-dict.

    This modifies the given options dictionary.

    Returns:
        Either the first un-parseable part, or None if everything went well.
    """

    in_color = False
    color_buffer = ""

    for part in seq.split(";"):
        if (
            part.isdigit()
            and int(part) in chain(range(30, 49), range(90, 108))
            and part not in ["39", "49"]
        ):
            in_color = True

        if in_color:
            color_buffer += part

            if _is_valid_color(color_buffer):
                key = (
                    "back" if _is_background_color(color_buffer) else "fore"
                ) + "ground"

                options[key] = color_buffer

                color_buffer = ""
                in_color = False

            else:
                color_buffer += ";"

            continue

        if part in SETTERS_TO_STYLES:
            options[SETTERS_TO_STYLES[part]] = True
            continue

        if part in UNSETTERS_TO_STYLES:
            key = UNSETTERS_TO_STYLES[part]

            if key in ["foreground", "background"]:
                options[key] = ""

            else:
                options[key] = False

                # Not sure why this is said to not be covered.
                if key == "bold":  # no-cov
                    options["dim"] = False

            continue

        return part

    return None


@dataclass(frozen=True)
class Span:  # pylint: disable=too-many-instance-attributes
    """A class to represent a piece of styled text.

    Note that spans are immutable, so to get new versions of an existing span you can
    use one of the `as_{style_name}` methods, or the more raw `mutate`.
    """

    text: str

    foreground: str = ""
    background: str = ""
    hyperlink: str = ""

    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False
    fast_blink: bool = False
    invert: bool = False
    conceal: bool = False
    strike: bool = False
    reset_after: bool = True

    _computed: str = field(init=False)
    _sequences: str = field(init=False)

    def __post_init__(self) -> None:
        sequences = self._generate_sequences()
        reset_end = "\x1b[0m" if self.reset_after and sequences != "" else ""

        combined = sequences + self.text + reset_end

        if self.hyperlink != "":
            combined = f"\x1b]8;;{self.hyperlink}\x1b\\{combined}\x1b]8;;\x1b\\"

        object.__setattr__(self, "_computed", combined)
        object.__setattr__(self, "_sequences", sequences)

    def __str__(self) -> str:
        return self._computed

    def __len__(self) -> int:
        return len(self.text)

    def __contains__(self, text: str) -> bool:
        return text in self.text

    def __getitem__(self, sli: int | slice) -> Span:
        return self.mutate(text=self.text[sli])

    def __repr__(self) -> str:
        name = type(self).__name__

        attributes = f"{self.text!r}, "
        truthy_fields = (
            field.name for field in fields(self) if getattr(self, field.name) is True
        )
        attributes += ", ".join(f"{name}=True" for name in truthy_fields)

        if self.foreground != "":
            attributes += f", foreground={self.foreground!r}"

        if self.background != "":
            attributes += f", background={self.background!r}"

        if self.hyperlink != "":
            attributes += f", hyperlink={self.hyperlink!r}"

        return f"{name}({attributes})"

    def _generate_sequences(self) -> str:
        """Generates the sequences represented by this Span."""

        sequences = ";".join([self.foreground, self.background])

        if sequences != "" and not sequences.endswith(";"):
            sequences += ";"

        for fld in fields(self):
            if not (fld.name in SETTERS and getattr(self, fld.name)):
                continue

            sequences += SETTERS[fld.name] + ";"

        if sequences == ";":
            return ""

        return f"\x1b[{sequences.strip(';')}m"

    @property
    def attrs(self) -> dict[str, bool | str]:
        """Returns a copy of the attributes that define this span."""

        return {
            "text": self.text,
            "bold": self.bold,
            "dim": self.dim,
            "italic": self.italic,
            "underline": self.underline,
            "blink": self.blink,
            "fast_blink": self.fast_blink,
            "invert": self.invert,
            "conceal": self.conceal,
            "strike": self.strike,
            "foreground": self.foreground,
            "background": self.background,
            "hyperlink": self.hyperlink,
        }

    @classmethod
    def yield_from(cls, line: str) -> Generator[Span, None, None]:
        """Generates Span objects from the given line."""

        # Add trailing ESC char to allow detection by regex
        if not line.endswith("\x1b"):
            line += "\x1b"

        options: dict[str, bool | str] = {}

        index = 0
        for mtch in RE_ANSI_STYLES.finditer(line):
            index = mtch.end()
            sequence, plain = mtch.groups()

            if (error_part := _parse_sequence(sequence, options)) is not None:
                raise ValueError(f"Could not parse {error_part!r} in {line!r}.")

            yield Span(plain, **options)  # type: ignore

        line = line.rstrip("\x1b")

        if index < len(line):
            yield Span(line[index:])

    @classmethod
    def first_from(cls, line: str) -> Span | None:
        """Returns the first object generated by `yield_from_line`."""

        for span in cls.yield_from(line):
            return span

        return None

    @classmethod
    def group(cls, line: list[str]) -> Iterable[Span]:
        """Groups similar characters next to eachother into spans.

        Two characters are similar if their styles match.
        """

        group = EMPTY_SPAN
        attrs = EMPTY_SPAN.attrs | {"text": ""}
        prev_str = ""

        for char in line:
            # If the previous is completely equal skip parsing to a span
            if str(char) == prev_str:
                group = group.mutate(text=group.text + char[-1])
                continue

            span = cls.first_from(char)

            if span is None:
                span = EMPTY_SPAN

            # Ignore text part of spans
            new_attrs = span.attrs | {"text": ""}

            if new_attrs == attrs:
                group = group.mutate(text=group.text + span.text)
                continue

            if group is not EMPTY_SPAN:
                yield group

            group = span
            prev_str = str(group.mutate(reset_after=False))
            attrs = new_attrs

        if group is not None:
            yield group

    def get_characters(
        self, always_include_sequence: bool = False
    ) -> Generator[str, None, None]:
        """Splits the Span into its characters.

        Args:
            always_include_sequence: Include the span's sequences before every
                character. If not set, only the first character will have them.

        Yields:
            Strings with the format `{sequences}{plain_character}`.
        """

        remaining_sequences = self._sequences
        for char in self.text[:-1]:
            yield remaining_sequences + char

            if not always_include_sequence:
                remaining_sequences = ""

        if self.text == "":
            return

        last = self.text[-1]

        if self._sequences != "" and self.reset_after:
            last = remaining_sequences + last + "\x1b[0m"

        yield last

    def get_svg_styles(self) -> dict[str, str]:
        """Returns this span's styling converted to SVG-compatible CSS."""

        css = {}

        for key, value in self.attrs.items():
            if key == "text":
                continue

            if not self.invert and key == "foreground" and value != "":
                assert isinstance(
                    value, str
                ), f"invalid type for foreground: {value!r}."

                css["fill"] = Color.from_ansi(value).hex

            if self.invert and key == "background" and value != "":
                assert isinstance(
                    value, str
                ), f"invalid type for background: {value!r}."

                css["fill"] = Color.from_ansi(value).hex

            elif key in STYLE_TO_CSS and value:
                key, value = STYLE_TO_CSS[key]
                css[key] = value

        return css

    def as_svg(
        self,
        font_size: int = 15,
        origin: tuple[float, float] = (0, 0),
        default_foreground: str = "#dddddd",
        default_background: str = "#212121",
        inline_styles: bool = False,
        cls: str | None = None,
    ) -> str:
        """Exports this span into a set of SVG tags (`<rect>`, `<text>`).

        Args:
            font_size: The font size used to calculate the background rectangle.
            origin: The origin of all coordinates in the output.
            default_foreground: If the span has no foreground color, this is
                substituted.
            default_background: If the span has no background color, this is
                substituted.
            inline_style: If set, the styles (color, font-weight...) for the span
                are included as a `style='...'` attribute. Use `get_svg_styles` to
                get these independently.
            cls: The classname inserted into the `class` attribute of the text tag.
        """

        char_width = round(font_size * SVG_CHAR_WIDTH, 4)
        rect_height = round(font_size * SVG_RECT_HEIGHT, 4)

        foreground = (
            Color.from_ansi(self.foreground).hex
            if self.foreground != ""
            else default_foreground
        )

        background = (
            Color.from_ansi(self.background).hex
            if self.background != ""
            else default_background
        )

        if self.invert:
            foreground, background = background, foreground

        length = len(self.text)

        x, y = origin

        if not _is_block(self.text):
            baseline_offset = SVG_RECT_BASELINE_OFFSET * font_size

        x = round(x, 2)
        y = round(y, 2)

        svg = (
            "<rect"
            + f" x='{x}'"
            + f" y='{y - baseline_offset}'"
            + f" fill='{background}'"
            + f" width='{round(char_width * length + 0.5, 2):.4f}'"
            + f" height='{rect_height}'"
            + "></rect>"
        )

        if inline_styles:
            styles = "; ".join(
                f"{key}:{value}" for key, value in self.get_svg_styles().items()
            )

        svg += (
            "<text  dy='-0.25em'"
            + f" x='{x}'"
            + f" y='{y + font_size}'"
            + (f" styles='{styles}'" if inline_styles else "")
            + (f" class='{cls}'" if cls is not None else "")
            + f">{_escape_html(self.text)}</text>"
        )

        return svg

    def mutate(self, **options: Any) -> Span:
        """Creates a new Span object, mutated with the given options."""

        config = self.attrs

        config.update(**options)

        return self.__class__(**config)  # type: ignore

    def split(self, char: str = " ") -> list[Span]:
        """Splits this span by the given character."""

        return [self.mutate(text=part) for part in self.text.split(char)]

    def as_color(self, color: Any) -> Span:
        """Returns a mutated Span object with the given color."""

        body = str(color)

        if _is_background_color(body):
            return self.mutate(background=body)

        return self.mutate(foreground=body)

    def as_bold(self, value: bool = True) -> Span:
        """Returns a mutated Span object, with `bold` set to the given value."""

        return self.mutate(bold=value)

    def as_dim(self, value: bool = True) -> Span:
        """Returns a mutated Span object, with `dim` set to the given value."""

        return self.mutate(dim=value)

    def as_italic(self, value: bool = True) -> Span:
        """Returns a mutated Span object, with `italic` set to the given value."""

        return self.mutate(italic=value)

    def as_underline(self, value: bool = True) -> Span:
        """Returns a mutated Span object, with `underline` set to the given value."""

        return self.mutate(underline=value)

    def as_blink(self, value: bool = True) -> Span:
        """Returns a mutated Span object, with `blink` set to the given value."""

        return self.mutate(blink=value)

    def as_fast_blink(self, value: bool = True) -> Span:
        """Returns a mutated Span object, with `fast_blink` set to the given value."""

        return self.mutate(fast_blink=value)

    def as_invert(self, value: bool = True) -> Span:
        """Returns a mutated Span object, with `invert` set to the given value."""

        return self.mutate(invert=value)

    def as_conceal(self, value: bool = True) -> Span:
        """Returns a mutated Span object, with `conceal` set to the given value."""

        return self.mutate(conceal=value)

    def as_strike(self, value: bool = True) -> Span:
        """Returns a mutated Span object, with `strike` set to the given value."""

        return self.mutate(strike=value)

    def as_hyperlink(self, value: str = "") -> Span:
        """Returns a mutated Span object, with `hyperlink` set to the given value."""

        return self.mutate(hyperlink=value)


EMPTY_SPAN = Span("")
