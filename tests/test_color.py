import pytest

from slate.core import ColorSpace
from slate.color import Color
from slate.color_info import COLOR_TABLE


def test_color_from_ansi():
    assert Color.from_ansi("31") == Color(
        COLOR_TABLE[1],
        _origin_colorspace="standard",
        _constructor="31",
    )
    assert Color.from_ansi("45") == Color(
        COLOR_TABLE[5],
        is_background=True,
        _origin_colorspace="standard",
        _constructor="45",
    )
    assert Color.from_ansi("93") == Color(
        COLOR_TABLE[11],
        _origin_colorspace="standard",
        _constructor="93",
    )
    assert Color.from_ansi("105") == Color(
        COLOR_TABLE[13],
        is_background=True,
        _origin_colorspace="standard",
        _constructor="105",
    )


def test_color_luminance():
    assert Color((38, 45, 125)).luminance == 0.03769509660602206
    assert Color((145, 121, 67)).luminance == 0.20099734269321143


def test_color_contrast():
    assert Color((255, 255, 255)).contrast == Color((35, 35, 35))
    assert Color((67, 10, 193), is_background=True).contrast == Color(
        (245, 245, 245),
        is_background=True,
    )


def test_color_lighten_darken():
    base = Color.from_ansi("141")

    assert base.lighten(1) == Color((183, 147, 255))
    assert base.darken(3, step_size=0.05) == Color((148, 114, 216))


def test_color_invalid():
    with pytest.raises(ValueError):
        Color((0, -1.25, 234))

    with pytest.raises(ValueError):
        Color.black().blend(Color.white(), alpha=0.01).darken(20)
