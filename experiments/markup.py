from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from functools import cached_property
from typing import Generator

from slate.span import SETTERS, Span

from color_info import COLOR_TABLE, CSS_COLORS

RE_MARKUP = re.compile(r"(?:\[(.+?)\])?([^\]\[]+)(?=\[|$)")

RE_256 = re.compile(r"^([\d]{1,3})$")
RE_HEX = re.compile(r"#?([0-9a-fA-F]{6})")
RE_RGB = re.compile(r"(\d{1,3};\d{1,3};\d{1,3})")

RE_COLOR = re.compile(
    r"(?:^@?([\d]{1,3})$)|(?:@?#?([0-9a-fA-F]{6}))|(@?\d{1,3};\d{1,3};\d{1,3})"
)


@dataclass(frozen=True)
class Color:
    rgb: tuple[int, int, int]
    is_background: bool = False

    @classmethod
    def from_ansi(cls, ansi: str) -> Color:
        """Creates a color instance from an ANSI sequence's body."""

        parts = ansi.split(";")
        if len(parts) > 3:
            is_background = parts[0].startswith("4")

            return Color((parts[2:]), is_background=is_background)

        ansi = parts[-1]

        # TODO: Handle garbage

        index = int(ansi)
        is_background = False

        # Convert indices to 16-color
        if len(parts) == 1:
            if 30 <= index < 38:
                index -= 30

            elif 40 <= index < 48:
                index -= 40
                is_background = True

            if 90 <= index < 98:
                index -= 82

            elif 100 <= index < 108:
                index -= 92
                is_background = True

        # print(
        #     f"{ansi} --> {index}",
        #     f"\x1b[{ansi}m#\x1b[0m --> \x1b[38;5;{index}m#\x1b[0m",
        # )
        return Color(COLOR_TABLE[index], is_background=is_background)

    @cached_property
    def ansi(self) -> str:
        return f"{38 + 10*self.is_background};2;{';'.join(map(str, self.rgb))}"

    @cached_property
    def luminance(self) -> float:
        """Returns this color's perceived luminance (brightness).

        From https://stackoverflow.com/a/596243
        """

        def _linearize(color: float) -> float:
            """Converts sRGB color to linear value."""

            if color <= 0.04045:
                return color / 12.92

            return ((color + 0.055) / 1.055) ** 2.4

        red, green, blue = float(self.rgb[0]), float(self.rgb[1]), float(self.rgb[2])

        red /= 255
        green /= 255
        blue /= 255

        red = _linearize(red)
        blue = _linearize(blue)
        green = _linearize(green)

        return 0.2126 * red + 0.7152 * green + 0.0722 * blue

    @cached_property
    def contrast(self) -> Color:
        """Returns a color (black or white) that complies with the W3C contrast ratio guidelines."""

        if self.luminance > 0.179:
            return Color((35, 35, 35))

        return Color((245, 245, 245))


def parse_color(color: str) -> str:
    background = color.startswith("@") * 10
    color = color.lstrip("@")

    if color.isdigit():
        index = int(color)

        if 0 <= index < 8:
            return str(30 + background + index)

        if 8 <= index < 16:
            index += 2  # Skip codes 38 & 48
            return str(80 + background + index)

        elif index < 256:
            return f"{38 + background};5;{index}"

        else:
            raise ValueError(
                f"Could not parse indexed color {color!r};"
                " it should be between 0 and 16, or 16 and 255."
            )

    if color in CSS_COLORS:
        color = CSS_COLORS[color]

    if color.startswith("#"):
        color = color.lstrip("#")

        color = ";".join(
            str(int(part, base=16)) for part in [color[:2], color[2:4], color[4:]]
        )

    return f"{38 + background};2;{color}"


def apply_auto_foreground(style_stack: dict[str, bool]) -> bool:
    back = style_stack.get("background")
    fore = style_stack.get("foreground")

    if style_stack["invert"]:
        back, fore = fore, back

    if not (fore is None and back is not None):
        return False

    style_stack["foreground"] = Color.from_ansi(back).contrast.ansi
    return True


def styled_from_markup(markup: str) -> Generator[Span, None, None]:
    style_stack = {style: False for style in SETTERS.keys()}

    for match in RE_MARKUP.finditer(markup):
        tags, plain = match.groups()

        if tags is None:
            tags = ""

        for tag in tags.split():
            unsetter = tag.startswith("/")
            tag = tag.lstrip("/")

            if RE_COLOR.match(tag) or tag.lstrip("@") in CSS_COLORS:
                key = "background" if tag.startswith("@") else "foreground"

                style_stack[key] = parse_color(tag)
                continue

            if unsetter and tag in ["fg", "bg"]:
                style_stack["foreground" if tag == "fg" else "background"] = ""
                continue

            if not tag in style_stack:
                print(f"Unknown tag {tag!r}")
                continue

            style_stack[tag] = not unsetter

        should_delete_foreground = apply_auto_foreground(style_stack)

        yield Span(plain, **style_stack)

        if should_delete_foreground:
            del style_stack["foreground"]


def mprint(markup: str) -> None:
    print("".join(map(str, styled_from_markup(markup))))


if __name__ == "__main__":
    args = sys.argv[1:]

    if args != "":
        for arg in args:
            mprint(arg)

    mprint("".join(f"[@{i}]{i:>3}" for i in range(16)))

    while True:
        print("".join(map(str, styled_from_markup(input("Markup: ")))))
