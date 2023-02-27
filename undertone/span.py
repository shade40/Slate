"""The Span class, a piece of formatted text for the terminal."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field, fields
from itertools import chain
from typing import Any, Generator

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
    "inverse": "27",
    "invisible": "28",
    "strikethrough": "29",
    "foreground": "39",
    "background": "49",
    "overline": "54",
}

UNSETTERS_TO_STYLES = {value: key for key, value in UNSETTERS.items()}

RE_ANSI_STYLES = re.compile(r"\x1b\[(?:(.*?))[mH]([^\x1b]+)(?=\x1b)")


@dataclass(frozen=True)
class Span:  # pylint: disable=too-many-instance-attributes
    """A class to represent a piece of styled text.

    Note that spans are immutable, so to get new versions of an existing span you can
    use one of the `as_{style_name}` methods, or the more raw `mutate`.
    """

    text: str

    foreground: str = ""
    background: str = ""

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

        object.__setattr__(self, "_computed", sequences + self.text + reset_end)
        object.__setattr__(self, "_sequences", sequences)

    def __str__(self) -> str:
        return self._computed

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

        return f"{name}({attributes})"

    @staticmethod
    def _is_background_color(body: str) -> bool:
        """Determines whether the given color body is a background.

        This assumes that the given body is already color.
        """

        return body.startswith("4") or (body.startswith("10") and len(body) > 2)

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

        return "\x1b[" + sequences.strip(";") + "m"

    @classmethod
    def yield_from(cls, line: str) -> Generator[Span, None, None]:
        """Generates Span objects from the given line."""

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

        def _parse_sequence(
            seq: str, options: dict[str, bool | str]
        ) -> dict[str, bool | str]:
            """Parses the given sequence into a option-dict."""

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
                            "back" if cls._is_background_color(color_buffer) else "fore"
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

                raise ValueError(f"Could not parse {part}.")

            return options

        # Add trailing ESC char to allow detection by regex
        if not line.endswith("\x1b"):
            line += "\x1b"

        options: dict[str, bool | str] = {}

        index = 0
        for mtch in RE_ANSI_STYLES.finditer(line):
            index = mtch.end()
            sequence, plain = mtch.groups()

            _parse_sequence(sequence, options)

            yield Span(plain, **options)  # type: ignore

        line = line.rstrip("\x1b")

        if index < len(line):
            yield Span(line[index:])

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

        last = self.text[-1]

        if self._sequences != "" and self.reset_after:
            last = remaining_sequences + last + "\x1b[0m"

        yield last

    def mutate(self, **options: Any) -> Span:
        """Creates a new Span object, mutated with the given options."""

        config = deepcopy(self.__dict__)
        del config["_computed"]
        del config["_sequences"]

        config.update(**options)

        return self.__class__(**config)

    def as_color(self, color: Any) -> Span:
        """Returns a mutated Span object with the given color."""

        body = str(color)

        if self._is_background_color(body):
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


if __name__ == "__main__":
    print(*Span.yield_from("\x1b[38;5;141;1mTest\x1b[7mInvert\x1b[0m"))
    print(list(Span("test", foreground="75", bold=True, italic=True).get_characters()))
