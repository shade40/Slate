"""The Color class, and some related utilities."""

from __future__ import annotations

from colorsys import hls_to_rgb, rgb_to_hls
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from math import sqrt
from typing import TYPE_CHECKING

from .color_info import COLOR_TABLE, NAMED_COLORS


if TYPE_CHECKING:
    from .terminal import Terminal
    from .core import ColorSpace

__all__ = ["Color", "color"]

OFF_WHITE = (245, 245, 245)
OFF_BLACK = (35, 35, 35)


def geometric_difference(
    first: tuple[int, int, int], second: tuple[int, int, int]
) -> float:
    """Gets the geometric difference of 2 RGB triplets.

    See https://en.wikipedia.org/wiki/Color_difference's Euclidian section.
    """

    red1, green1, blue1 = first
    red2, green2, blue2 = second

    redmean = (red1 + red2) // 2

    delta_red = red1 - red2
    delta_green = green1 - green2
    delta_blue = blue1 - blue2

    return sqrt(
        (2 + (redmean / 256)) * (delta_red ** 2)
        + 4 * (delta_green ** 2)
        + (2 + (255 - redmean) / 256) * (delta_blue ** 2)
    )


def calculate_luminance(base: Color) -> float:
    """Calculates the given color's luminance (objective brightness).

    Source: https://stackoverflow.com/a/596243.
    """

    def _linearize(val: float) -> float:
        """Converts sRGB color to linear value."""

        if val <= 0.04045:
            return val / 12.92

        return float(((val + 0.055) / 1.055) ** 2.4)

    red = _linearize(base.rgb[0] / 255)
    green = _linearize(base.rgb[1] / 255)
    blue = _linearize(base.rgb[2] / 255)

    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def calculate_brightness(base: Color) -> float:
    """Returns the given color's brightness (perceived luminance)..

    From https://stackoverflow.com/a/56678483
    """

    if base.luminance <= (216 / 24389):
        brightness = base.luminance * (24389 / 27)

    else:
        brightness = base.luminance ** (1 / 3) * 116 - 16

    return brightness / 100


def calculate_contrast(
    base: Color,
    white: Color | None = None,
    black: Color | None = None,
) -> Color:
    """Calculates the given color's black/white contrast.

    Args:
        base: The color that's used for the calculation.
        white: The color returned for "dark" bases. Defaults to (245, 245, 245).
        black: The color returned for "light" bases. Defaults to (35, 35, 35).

    Returns:
        A color that satisfies W3C's contrast guidelines when painted on top of `base`.
    """

    if base.luminance > 0.179:
        return (black or DEFAULT_BLACK).as_background(base.is_background)

    return (white or DEFAULT_WHITE).as_background(base.is_background)


def calculate_triadic_group(base: Color) -> tuple[Color, Color, Color]:
    """Returns the triadic group this color is within."""

    return base, base.hue_shift(1 / 3), base.hue_shift(2 / 3)


def calculate_analogous_group(base: Color) -> tuple[Color, Color, Color]:
    """Returns the analogous group this color is within."""

    return base, base.hue_shift(1 / 12), base.hue_shift(2 / 12)


def calculate_tetradic_group(base: Color) -> tuple[Color, Color, Color, Color]:
    """Returns the triadic group this color is within."""

    return base, base.hue_shift(1 / 4), base.complement, base.hue_shift(3 / 4)


@dataclass(frozen=True)
class Color:  # pylint: disable = too-many-instance-attributes
    """A class that represents an RGB value."""

    rgb: tuple[int, int, int]
    is_background: bool = False
    alpha: float = 1.0

    luminance: float = field(init=False)
    brightness: float = field(init=False)
    hls: tuple[float, float, float] = field(init=False)
    hex: str = field(init=False)

    _origin_colorspace: str = "true_color"
    _constructor: str | None = None

    def __post_init__(self) -> None:
        def _set_field(
            key: str, value: float | str | tuple[float, float, float] | ColorSpace
        ) -> None:
            object.__setattr__(self, key, value)

        if any(not 0 <= val < 256 for val in self.rgb):
            raise ValueError(
                "Color RGB values must be between 0 and 256,"
                + f" got {self.rgb!r} from {self._constructor!r}.",
            )

        _set_field("luminance", calculate_luminance(self))
        _set_field("brightness", calculate_brightness(self))
        _set_field("hls", rgb_to_hls(*(val / 256 for val in self.rgb)))
        _set_field("hex", "#" + "".join(f"{i:02X}" for i in self.rgb))

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(rgb={self.rgb}"
            + f", alpha={self.alpha}" * (self.alpha != 1.0)
            + ")"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Color):
            return NotImplemented

        return self.rgb == other.rgb and self.alpha == other.alpha

    @classmethod
    def from_ansi(cls, ansi: str, alpha: float = 1.0) -> Color:
        """Creates a color instance from an ANSI sequence's body."""

        parts = ansi.split(";")

        if "." in parts[-1]:
            alpha = float(parts[-1])
            parts.pop()

        is_background = parts[0].startswith("4")

        if len(parts) > 3:
            if parts[:2] not in [["38", "2"], ["48", "2"]]:
                raise ValueError(
                    "Only colors with prefixes `38;2` and `48;2` are allowed,"
                    + f" got {ansi!r}."
                )

            return Color(
                (int(parts[2]), int(parts[3]), int(parts[4])),
                is_background=is_background,
                alpha=alpha,
                _origin_colorspace="true_color",
                _constructor=";".join(parts),
            )

        end = parts[-1]
        color_space = "eight_bit"

        index = int(end)

        # Convert indices to 16-color
        if len(parts) == 1:
            color_space = "standard"

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

        if not 0 <= index < 256:
            raise ValueError(
                "Color ANSI index must be between 0 and 256,"
                + f" got {index!r} from {ansi!r}."
            )

        return Color(
            COLOR_TABLE[index],
            is_background=is_background,
            alpha=alpha,
            _origin_colorspace=color_space,
            _constructor=ansi,
        )

    @classmethod
    def from_hex(cls, hexstring: str, alpha: float = 1.0) -> Color:
        """Generates a Color instance from a hex string."""

        hexstring = hexstring.lstrip("#")

        return cls(
            (
                int(hexstring[:2], base=16),
                int(hexstring[2:4], base=16),
                int(hexstring[4:], base=16),
            ),
            alpha=alpha,
            _constructor="#" + hexstring,
        )

    @classmethod
    def black(cls, is_background: bool = False) -> Color:
        """Returns a 100% black."""

        if is_background:
            return BLACK.as_background(is_background)

        return BLACK

    @classmethod
    def white(cls, is_background: bool = False) -> Color:
        """Returns a 100% white."""

        if is_background:
            return WHITE.as_background(is_background)

        return WHITE

    @cached_property
    def ansi(self) -> str:
        """Returns the ANSI code that represents this color."""

        from .terminal import (  # pylint: disable=import-outside-toplevel, cyclic-import
            terminal,
        )
        from .core import (  # pylint: disable=import-outside-toplevel, cyclic-import
            ColorSpace,
        )

        lead = 38 + 10 * self.is_background

        origin = ColorSpace(self._origin_colorspace)

        if terminal.color_space >= origin and (
            self._constructor is not None and not self._constructor.startswith("#")
        ):
            return self._constructor

        if terminal.color_space is ColorSpace.TRUE_COLOR:
            return f"{lead};2;{';'.join(map(str, self.rgb))}"

        if terminal.color_space is ColorSpace.NO_COLOR:
            return f"{lead};5;{min(232 + self.brightness*23, 255):.0f}"

        if terminal.color_space is ColorSpace.EIGHT_BIT:
            # Normalize the color values
            red, green, blue = (x / 255 for x in self.rgb)

            # Calculate the eight-bit color index
            index = 16
            index += 36 * round(red * 5)
            index += 6 * round(green * 5)
            index += round(blue * 5)

            return f"{lead};5;{index}"

        if terminal.color_space is ColorSpace.STANDARD:
            rgb = self.rgb

            index = min(
                range(16), key=lambda i: geometric_difference(rgb, COLOR_TABLE[i])
            )

            if index > 7:
                index += 82
            else:
                index += 30

            if self.is_background:
                index += 10

            return f"{index}"

        raise NotImplementedError

    @cached_property
    def contrast(self) -> Color:
        """Returns this given color's black/white contrast color."""

        return calculate_contrast(self)

    @cached_property
    def complement(self) -> Color:
        """Returns the complement of this color."""

        if self.hls[0] == 0.0:
            return Color((255, 255, 255)) if self.hls[1] == 0.0 else Color((0, 0, 0))

        return self.hue_shift(0.5)

    @cached_property
    def triadic_group(self) -> tuple[Color, Color, Color]:
        """Returns the triadic group this color is part of."""

        return calculate_triadic_group(self)

    @cached_property
    def analogous_group(self) -> tuple[Color, Color, Color]:
        """Returns the analogous group this color is part of."""

        return calculate_analogous_group(self)

    @cached_property
    def tetradic_group(self) -> tuple[Color, Color, Color, Color]:
        """Returns the tetradic group this color is part of."""

        return calculate_tetradic_group(self)

    def as_alpha(self, value: float) -> Color:
        """Returns this color with the given alpha."""

        return Color(self.rgb, alpha=value, is_background=self.is_background)

    def lighten(self, shade_count: int, step_size: float = 0.1) -> Color:
        """Returns a lighter version of this color.

        The calculation is done by blending white with an alpha of:

            `shade_count * step_size`
        """

        return self.blend(Color.white(), alpha=shade_count * step_size)

    def darken(self, shade_count: int, step_size: float = 0.1) -> Color:
        """Returns a darker version of this color.

        The calculation is done by blending black with an alpha of:

            `shade_count * step_size`
        """

        return self.blend(Color.black(), alpha=shade_count * step_size)

    def as_background(self, setting: bool = True, alpha: int | None = None) -> Color:
        """Returns this color, with the given background setting."""

        if self.is_background == setting:
            return self

        return Color(self.rgb, is_background=setting, alpha=alpha or self.alpha)

    def hue_shift(self, amount: float) -> Color:
        """Returns a color with a hue offset of the given amount.

        Args:
            amount: The difference in hue. Given as 0-1f.

        Returns:
            This color, with its hue shifted.
        """

        hue, lightness, saturation = self.hls
        rgb = hls_to_rgb((hue + amount) % 1, lightness, saturation)

        return Color(
            (int(255 * rgb[0]), int(255 * rgb[1]), int(255 * rgb[2])),
            is_background=self.is_background,
        )

    @lru_cache
    def blend(
        self, other: Color, alpha: float, is_background: bool | None = None
    ) -> Color:
        """Blends this color with other by a certain alpha.

        Args:
            other: The color to blend into.
            alpha: How closely we should blend to the given color. For example,
                0.9 would be 10% self, 90% other.

        Returns:
            The blended color.
        """

        if is_background is None:
            is_background = self.is_background

        red1, green1, blue1 = self.rgb
        red2, green2, blue2 = other.rgb

        return Color(
            (
                int(red1 + (red2 - red1) * alpha),
                int(green1 + (green2 - green1) * alpha),
                int(blue1 + (blue2 - blue1) * alpha),
            ),
            is_background=is_background,
        )

    def blend_complement(self, alpha: float) -> Color:
        """Blends this color by its complement.

        See `blend` for more info.

        Args:
            alpha: How closely we should blend into the complement.
        """

        return self.blend(self.complement, alpha)


def color(
    description: str | tuple[int, int, int] | tuple[int, int, int, float]
) -> Color:
    """Creates a color from the given description.

    This calls either the Color constructor, `Color.from_ansi` or
    `Color.from_hex`, depending on the given value.
    """

    if isinstance(description, tuple):
        alpha = 1.0
        triplet: tuple[int, int, int]

        if len(description) == 4:
            alpha = description[-1]
            triplet = description[:-1]  # type: ignore
        else:
            triplet = description  # type: ignore

        return Color(triplet, alpha=alpha)

    if isinstance(description, str):
        if description.startswith("#"):
            alpha = 1.0

            if len(description) == 9:
                alpha = int(description[-2:], base=16) / 255
                description = description[:-2]

            return Color.from_hex(description, alpha=alpha)

        alpha = 1.0
        parts = description.split(";")

        if "." in parts[-1]:
            description = ";".join(parts[:-1])
            alpha = float(parts[-1])

        if description in NAMED_COLORS:
            return Color.from_hex(NAMED_COLORS[description], alpha=alpha)

        return Color.from_ansi(description, alpha=alpha)

    raise ValueError(f"unknown descriptor {description!r}")


WHITE = Color((255, 255, 255))
BLACK = Color((0, 0, 0))

DEFAULT_WHITE = Color(OFF_WHITE)
DEFAULT_BLACK = Color(OFF_BLACK)
