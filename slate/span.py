"""The Span class, a piece of formatted text for the terminal."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from functools import lru_cache
from itertools import chain
from typing import Any, Generator, Iterable, TypedDict
from html import escape

from .color import Color, color

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


class SpanConfig(TypedDict):
    """A dictionary used to store span configuration."""

    text: str
    bold: bool
    dim: bool
    italic: bool
    underline: bool
    blink: bool
    fast_blink: bool
    invert: bool
    conceal: bool
    strike: bool
    foreground: Color | None
    background: Color | None
    hyperlink: str


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
        return len(parts) in [5, 6]

    if parts[1] == "5":
        return len(parts) in [3, 4]

    return False


def _parse_sequence(
    seq: str, options: dict[str, str | bool | Color | None]
) -> None | str:
    """Parses the given sequence and inserts it into the given SpanConfig..

    This modifies the given options dictionary.

    Returns:
        Either the first un-parseable part, or None if everything went well.
    """

    in_color = False
    color_buffer = ""

    parts = seq.split(";")

    for i, part in enumerate(parts):
        if (
            part.isdigit()
            and int(part) in chain(range(30, 49), range(90, 108))
            and part not in ["39", "49"]
        ):
            in_color = True

        if in_color:
            color_buffer += part

            if _is_valid_color(color_buffer) and (
                len(parts) >= i or "." not in parts[i + 1]
            ):
                key = (
                    "back" if _is_background_color(color_buffer) else "fore"
                ) + "ground"

                options[key] = Color.from_ansi(color_buffer)

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
                options[key] = None

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

    foreground: Color | None = None
    background: Color | None = None
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
    _colorless_sequences: str = field(init=False)

    def __post_init__(self) -> None:
        sequences, colorless_sequences = self._generate_sequences()
        reset_end = "\x1b[0m" if self.reset_after and sequences != "" else ""

        combined = sequences + self.text + reset_end

        if self.hyperlink != "":
            combined = f"\x1b]8;;{self.hyperlink}\x1b\\{combined}\x1b]8;;\x1b\\"

        object.__setattr__(self, "_computed", combined)
        object.__setattr__(self, "_sequences", sequences)
        object.__setattr__(self, "_colorless_sequences", colorless_sequences)

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

        if self.foreground is not None:
            attributes += f", foreground={self.foreground!r}"

        if self.background is not None:
            attributes += f", background={self.background!r}"

        if self.hyperlink != "":
            attributes += f", hyperlink={self.hyperlink!r}"

        return f"{name}({attributes})"

    def _generate_sequences(self) -> tuple[str, str]:
        """Generates the sequences represented by this Span."""

        sequences = ""

        for fld in fields(self):
            if not (fld.name in SETTERS and getattr(self, fld.name)):
                continue

            sequences += SETTERS[fld.name] + ";"

        colorless = sequences.strip(";")

        colors = []

        if self.foreground is not None:
            colors.append(self.foreground.ansi)

        if self.background is not None:
            colors.append(self.background.ansi)

        total = ";".join(colors)

        if colorless:
            total += ";" * (len(total) != 0) + colorless

        return (
            f"\x1b[{total}m" if total else "",
            f"\x1b[{colorless}m" if colorless else "",
        )

    @property
    def attrs(self) -> SpanConfig:
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

        options: dict[str, str | bool | Color | None] = {}

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

    @lru_cache
    def get_characters(
        self, exclude_color: bool = False, always_include_sequence: bool = False
    ) -> list[str]:
        """Splits the Span into its characters.

        Args:
            always_include_sequence: Include the span's sequences before every
                character. If not set, only the first character will have them.

        Returns:
            A list of strings with the format `{sequences}{plain_character}`.
        """

        sequences = self._colorless_sequences if exclude_color else self._sequences
        remaining_sequences = sequences

        chars = []

        for char in self.text[:-1]:
            chars.append(remaining_sequences + char)

            if not always_include_sequence:
                remaining_sequences = ""

        if self.text != "":
            last = self.text[-1]

            if sequences != "" and self.reset_after:
                last = remaining_sequences + last + "\x1b[0m"

            chars.append(last)

        return chars

    def get_svg_styles(self) -> dict[str, str]:
        """Returns this span's styling converted to SVG-compatible CSS."""

        css = {}

        for key, value in self.attrs.items():
            if key == "text":
                continue

            if not self.invert and key == "foreground" and isinstance(value, Color):
                css["fill"] = value.hex

            if self.invert and key == "background" and isinstance(value, Color):
                css["fill"] = value.hex

            elif key in STYLE_TO_CSS and value:
                key, value = STYLE_TO_CSS[key]
                css[key] = value

        return css

    def as_svg(  # pylint: disable=too-many-arguments, too-many-locals
        self,
        font_size: int = 15,
        origin: tuple[float, float] = (0, 0),
        default_foreground: Color = color("#dddddd"),
        default_background: Color = color("#212121"),
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
            self.foreground if self.foreground is not None else default_foreground
        )

        background = (
            self.background if self.background is not None else default_background
        )

        if self.invert:
            foreground, background = background, foreground

        length = len(self.text)

        x, y = origin

        if not _is_block(self.text):
            baseline_offset = SVG_RECT_BASELINE_OFFSET * font_size
        else:
            baseline_offset = 0

        x = round(x, 2)
        y = round(y, 2)

        svg = (
            "<rect"
            + f" x='{x}'"
            + f" y='{y - baseline_offset}'"
            + f" fill='{background.hex}'"
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
            + f" fill='{foreground.hex}'"
            + (f" styles='{styles}'" if inline_styles else "")
            + (f" class='{cls}'" if cls is not None else "")
            + f">{_escape_html(self.text)}</text>"
        )

        return svg

    def mutate(self, **options: Any) -> Span:
        """Creates a new Span object, mutated with the given options."""

        config = self.attrs
        config.update(**options)  # type: ignore

        return self.__class__(**config)

    def split(self, char: str = " ") -> list[Span]:
        """Splits this span by the given character."""

        return [self.mutate(text=part) for part in self.text.split(char)]

    def as_color(self, value: Color | str | tuple[int, int, int]) -> Span:
        """Returns a mutated Span object with the given color."""

        if not isinstance(value, Color):
            value = color(value)

        if value.is_background:
            return self.mutate(background=value)

        return self.mutate(foreground=value)

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
