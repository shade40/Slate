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
    SHOW_CURSOR,
    START_ALT_BUFFER,
    ColorSpace,
    get_color_space,
    get_default_color,
    getch_timeout,
    set_echo,
)
from .event import Event
from .screen import Screen
from .span import Span

RE_PIXEL_SIZE = re.compile(r"\x1b\[4;([\d]+);([\d]+)t")


@dataclass
class Terminal:
    """An object to read & write data to and from the terminal."""

    stream: TextIO = sys.stdout
    origin: tuple[int, int] = (1, 1)
    resolution_fallback: tuple[int, int] = (1280, 720)

    on_resize: Event = field(init=False)
    _screen: Screen = field(init=False)
    _previous_size: tuple[int, int] | None = None
    _forced_color_space: ColorSpace | None = None

    def __post_init__(self) -> None:
        self._screen = Screen(*self.size)

        self.on_resize = Event("Terminal Resized")
        self.on_resize += self._screen.resize

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

    @cached_property
    def supports_synchronized_update(self) -> bool:  # no-cov
        """Queries whether this terminal supports synchronized output.

        https://gist.github.com/christianparpart/d8a62cc1ab659194337d73e399004036
        """

        self.write_control(QUERY_SYNCHRONIZED_UPDATE)

        if not (response := getch_timeout(0.05)):
            return False

        return response in ["\x1b[?2026;1$y", "\x1b[?2026;2$y"]

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

        Arguments:
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
        output = getch_timeout(
            0.05,
            default=f"\x1b[4;{';'.join(map(str, reversed(self.resolution_fallback)))}t",
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

    def get_fg_color(self) -> str:
        """Returns the foreground color of the terminal."""

        return get_default_color("10", stream=self.stream)

    def get_bg_color(self) -> str:
        """Returns the background color of the terminal."""

        return get_default_color("11", stream=self.stream)

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

    # @contextmanager
    # def buffered_writer(
    #     self, offset: tuple[int, int] = (0, 0), flush: bool = True
    # ) -> Generator[StringIO, None, None]:
    #     """Creates a StringIO and writes it to the terminal on exit."""

    #     buffer = StringIO()

    #     try:
    #         yield buffer

    #     finally:
    #         self.write(buffer.getvalue(), offset=offset, flush=flush)

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
            if self.supports_synchronized_update:
                self.write_control(BEGIN_SYNCHRONIZED_UPDATE)

            yield

        finally:
            if self.supports_synchronized_update:
                self.write_control(END_SYNCHRONIZED_UPDATE)
