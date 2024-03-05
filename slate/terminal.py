"""The Terminal class, which is the primary surface to interact with the emulator."""

from __future__ import annotations

import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cached_property
from shutil import get_terminal_size
from typing import Generator, Iterable, TextIO

from .core import (
    BEGIN_SYNCHRONIZED_UPDATE,
    END_ALT_BUFFER,
    END_SYNCHRONIZED_UPDATE,
    HIDE_CURSOR,
    QUERY_SYNCHRONIZED_UPDATE,
    RESTORE_TITLE,
    SET_TITLE,
    SHOW_CURSOR,
    START_ALT_BUFFER,
    STORE_TITLE,
    ColorSpace,
    get_color_space,
    get_default_color,
    getch_timeout,
    set_echo,
)
from .color import Color
from .event import Event
from .screen import Screen
from .span import Span, SVG_CHAR_WIDTH, SVG_CHAR_HEIGHT

__all__ = [
    "Terminal",
    "terminal",
]

RE_PIXEL_SIZE = re.compile(r"\x1b\[4;([\d]+);([\d]+)t")

SVG_TEMPLATE = """
<svg width="{total_width}" height="{total_height}"
    viewBox="0 0 {total_width} {total_height}" xmlns="http://www.w3.org/2000/svg">
    <style type="text/css">
        text {{
            font-size: {font_size}px;
            font-family: Menlo, 'DejaVu Sans Mono', consolas, 'Courier New', monospace;
            font-feature-settings: normal;
            /* Inline SVGs are `antialiased` by default, while `src=`-d ones are `auto`.*/
            -webkit-font-smoothing: auto;
        }}
{stylesheet}
    </style>
{background}
<g transform="translate({screen_margin_x}, {screen_margin_y})">
{screen}
</g>
</svg>"""


@dataclass
class Terminal:  # pylint: disable=too-many-public-methods, too-many-instance-attributes
    """An object to read & write data to and from the terminal."""

    stream: TextIO = sys.stdout
    origin: tuple[int, int] = (1, 1)
    resolution_fallback: tuple[int, int] = (1280, 720)

    on_resize: Event[tuple[int, int]] = field(init=False)
    on_color_space_set: Event[ColorSpace | None] = field(init=False)

    _screen: Screen = field(init=False)
    _previous_size: tuple[int, int] | None = None
    _forced_color_space: ColorSpace | None = None
    _custom_title: str | None = None

    def __post_init__(self) -> None:
        self._screen = Screen(*self.size)

        self.on_resize = Event("terminal resized")

        def _on_resize(data: tuple[int, int]) -> bool:
            self._screen.resize(data)

            return True

        self.on_resize += _on_resize
        self.on_color_space_set = Event("color space set")

    @property
    def color_space(self) -> ColorSpace:
        """Returns the best color space available on the system.

        If `NO_COLOR` is set, ColorSpace.NO_COLOR is returned.
        """

        if self._forced_color_space is not None:
            return self._forced_color_space

        return get_color_space()

    @color_space.setter
    def color_space(self, new: ColorSpace | None) -> None:
        """Overrides the queried color space setting."""

        self._forced_color_space = new
        self.on_color_space_set(new)

    @cached_property
    def supports_synchronized_update(self) -> bool:  # no-cov
        """Queries whether this terminal supports synchronized output.

        https://gist.github.com/christianparpart/d8a62cc1ab659194337d73e399004036
        """

        self.write_control(QUERY_SYNCHRONIZED_UPDATE)

        if not (response := str(getch_timeout(0.05))):
            return False

        return response in ["\x1b[?2026;1$y", "\x1b[?2026;2$y"]

    @cached_property
    def foreground_color(self) -> Color:
        """Returns the terminal's default foreground color."""

        with self.no_echo():
            return get_default_color("10", stream=self.stream)

    @cached_property
    def background_color(self) -> Color:
        """Returns the terminal's default background color."""

        with self.no_echo():
            return get_default_color("11", stream=self.stream)

    @property
    def size(self) -> tuple[int, int]:
        """Returns the size (width, height) of the terminal."""

        size = get_terminal_size()

        if self._previous_size is not None and size != self._previous_size:
            self.on_resize(size)

        self._previous_size = size

        return size

    @property
    def width(self) -> int:
        """Returns the width of the terminal."""

        return self.size[0]

    @property
    def height(self) -> int:
        """Returns the height of the terminal."""

        return self.size[1]

    @property
    def isatty(self) -> bool:  # no-cov
        """Returns whether this terminal represents a TTY."""

        try:
            return self.stream.isatty()

        # TTY has most likely closed, like at the end of a pytest run.
        except ValueError:
            return False

    @property
    def resolution(self) -> tuple[int, int]:  # no-cov
        """Gets the pixel resolution of the terminal.

        Args:
            fallback: Returned when something went wrong. Usually this means the
                terminal is not a TTY, or it sent a garbled response.

        Returns:
            A tuple of (width, height) of the terminal 'screen', in pixels.
        """

        if not self.isatty:
            return self.resolution_fallback

        self.write_control("\x1b[14t")

        # Some terminals may not respond to a pixel size query, so we send
        # a timed-out getch call with a fallback
        output = str(
            getch_timeout(
                0.05,
                default=f"\x1b[4;{';'.join(map(str, reversed(self.resolution_fallback)))}t",
            )
        )
        mtch = RE_PIXEL_SIZE.match(output)

        if mtch is not None:
            return (int(mtch[2]), int(mtch[1]))

        return self.resolution_fallback

    @property
    def cursor(self) -> tuple[int, int]:
        """Sets/gets the terminal's screen's cursor."""

        return self._screen.cursor

    @cursor.setter
    def cursor(self, new: tuple[int, int]) -> None:
        """Sets/gets the terminal's screen's cursor."""

        self._screen.cursor = new

    @contextmanager
    def alt_buffer(
        self, hide_cursor: bool = True
    ) -> Generator[None, None, None]:  # no-cov
        """Manages an alternate buffer in the terminal."""

        try:
            self.write_control(START_ALT_BUFFER)

            if hide_cursor:
                self.show_cursor(False)

            yield

        finally:
            self.write_control(END_ALT_BUFFER)
            self.write_control(RESTORE_TITLE)

            if hide_cursor:
                self.show_cursor(True)

    @contextmanager
    def no_echo(self) -> Generator[None, None, None]:  # no-cov
        """Temporarily disables echoing in the terminal."""

        try:
            set_echo(False)
            yield

        finally:
            set_echo(True)

    @contextmanager
    def report_mouse(self) -> Generator[None, None, None]:  # no-cov
        """Sets mouse reporting for the duration of the context manager."""

        try:
            self.set_report_mouse(True)
            yield

        finally:
            self.set_report_mouse(False)

    @contextmanager
    def batch(self) -> Generator[None, None, None]:  # no-cov
        """A context within which every `write` is batched into one draw call.

        This implements the [synchronized update]
        (https://gist.github.com/christianparpart/d8a62cc1ab659194337d73e399004036)
        protocol.
        """

        try:
            self.write_control(BEGIN_SYNCHRONIZED_UPDATE)

            yield

        finally:
            self.write_control(END_SYNCHRONIZED_UPDATE)

    def set_title(self, new: str | None) -> None:
        """Sets the terminal's title.

        The first time it is set within an application, the previous value will be
        stored. When the application finishes (i.e. `alt_buffer` quits) the original
        title is restored.
        """

        if new is None:
            self.write_control(RESTORE_TITLE)
            self._custom_title = None
            return

        if not self._custom_title:
            self.write_control(STORE_TITLE)

        self.write_control(SET_TITLE.format(title=new))
        self._custom_title = new

    def show_cursor(self, value: bool = True) -> None:  # no-cov
        """Shows or hides the terminal's cursor."""

        if value:
            self.write_control(SHOW_CURSOR)

        else:
            self.write_control(HIDE_CURSOR)

    def set_report_mouse(self, value: bool = True) -> None:  # no-cov
        """Starts or stops listening to SGR 1006 mouse events."""

        if value:
            self.write_control("\x1b[?1006h\x1b[?1002h\x1b[?1003h")

        else:
            self.write_control("\x1b[?1006l\x1b[?1002l\x1b[?1003l")

    def clear(self, fillchar: str = " ") -> None:
        """Clears the screen's entire matrix.

        Args:
            fillchar: The character to fill the matrix with.
        """

        self._screen.clear(fillchar)

    def write(
        self,
        data: Iterable[Span] | str,
        cursor: tuple[int, int] | None = None,
        force_overwrite: bool = False,
    ) -> int:
        """Writes a span to the screen at the given cursor position.

        Args:
            data: The data to write. If passed as a string, `Span.yield_from` is used
                to get a generator of `Span` objects.
            cursor: The location of the screen to start writing at, anchored to the
                top-left. If not given, the screen's last used cursor is used.
            force_overwrite: If set, each of the characters written will be registered
                as a change.

        Returns:
            The number of cells that have been updated as a result of the write.
        """

        if isinstance(data, str):
            data = Span.yield_from(data)

        changes = self._screen.write(
            data, cursor=cursor, force_overwrite=force_overwrite
        )

        return changes

    def write_control(self, sequence: str, flush: bool = True) -> None:
        """Writes some control sequence to the terminal.

        This method writes directly to the stream, bypassing the screen mechanism.

        Args:
            sequence: The control sequence to write.
            flush: If set, the stream will be flushed after writing.
        """

        self.stream.write(sequence)

        if flush:  # no-cov
            self.stream.flush()

    def draw(self, redraw: bool = False) -> None:
        """Draws the current screen to the terminal.

        Args:
            redraw: If set, the screen will do a complete redraw, instead of only
                writing changes.
        """

        self.stream.write(self._screen.render(origin=self.origin, redraw=redraw))
        self.stream.flush()

    def bell(self) -> None:  # no-cov
        """Plays the terminal's bell sound."""

        self.write_control("\a")

    def export_svg(
        self,
        font_size: int = 15,
        default_foreground: Color | None = None,
        default_background: Color | None = None,
    ) -> str:
        """Exports an SVG image that represents this terminal.

        Internally, this exports the terminal's screen and wraps it in a terminal-like
        style.

        Args:
            font_size: The font size used for the screen's content.
            default_foreground: For each character on the screen, this color is used
                when it doesn't have a foreground color.
            default_background: For each character on the screen, this color is used
                when it doesn't have a background color.
        """

        background_color = default_background or self.background_color

        screen, screen_stylesheet = self._screen.export_svg_with_styles(
            origin=(0, 0),
            font_size=font_size,
            default_foreground=default_foreground or self.foreground_color,
            default_background=background_color,
        )

        margin_x = 16
        margin_y = 16

        total_width = self.width * SVG_CHAR_WIDTH * font_size + 2 * margin_x
        total_height = self.height * SVG_CHAR_HEIGHT * font_size + 2 * margin_y

        background = (
            f"<rect width='{total_width}' height='{total_height}'"
            + f" fill='#{background_color.hex}' rx='9px'></rect>"
        )

        return SVG_TEMPLATE.format(
            font_size=font_size,
            screen_margin_x=margin_x,
            screen_margin_y=margin_y,
            total_width=total_width,
            total_height=total_height,
            stylesheet=screen_stylesheet,
            background=background,
            chrome="",
            screen=screen,
        )


terminal = Terminal()
