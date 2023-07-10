"""A set of non-object specific terminal API implementations.

Most of these are best used from the `Terminal` object.
"""

from __future__ import annotations

import os
import re
import signal
import sys
from codecs import getincrementaldecoder
from contextlib import contextmanager
from enum import Enum
from select import select
from typing import IO, Any, AnyStr, Generator, Literal, TextIO
from io import StringIO

from .key_names import NT_KEY_NAMES, POSIX_KEY_NAMES
from .span import Span

try:
    import msvcrt

except ImportError:
    import termios
    import tty

    if os.name != "posix":  # no-cov
        raise NotImplementedError(f"Platform {os.name!r} is not supported.") from None

__all__ = [
    "ColorSpace",
    "getch",
    "getch_timeout",
    "get_default_color",
    "get_color_space",
    "feed",
    "set_echo",
    "timeout",
    "width",
]

# SGR (1006) mouse event decoding
MOUSE_EVENTS = {
    "0": "left_click",
    "2": "right_click",
    "16": "ctrl_left_click",
    "18": "ctrl_right_click",
    "32": "left_drag",
    "34": "right_drag",
    "48": "ctrl_left_drag",
    "50": "ctrl_right_drag",
    "35": "hover",
    "39": "shift_hover",
    "51": "ctrl_hover",
    "64": "scroll_up",
    "65": "scroll_down",
    "66": "scroll_left",
    "67": "scroll_right",
    "70": "shift_scroll_up",
    "71": "shift_scroll_down",
    "80": "ctrl_scroll_up",
    "81": "ctrl_scroll_down",
}

START_ALT_BUFFER = "\x1b[?1049h"
END_ALT_BUFFER = "\x1b[?1049l"
SHOW_CURSOR = "\x1b[?25h"
HIDE_CURSOR = "\x1b[?25l"

STORE_TITLE = "\x1b[22;0t"
SET_TITLE = "\x1b]0;{title}\a"
RESTORE_TITLE = "\x1b[23;0t"

QUERY_SYNCHRONIZED_UPDATE = "\x1b[?2026$p"
BEGIN_SYNCHRONIZED_UPDATE = "\x1b[?2026$h"
END_SYNCHRONIZED_UPDATE = "\x1b[?2026$l"

RE_PALETTE_REPLY = re.compile(
    r"\x1b]((?:10)|(?:11));rgb:([0-9a-f]{4})\/([0-9a-f]{4})\/([0-9a-f]{4})\x1b\\"
)

RE_ANSI = re.compile(r"(?:\x1b\[(.*?)[mH])|(?:\x1b\](.*?)\x1b\\)|(?:\x1b_G(.*?)\x1b\\)")

DEFAULT_COLOR_DEFAULTS = {"10": "dedede", "11": "141414"}

feeder_stream = StringIO()


def width(text: str | Span) -> int:
    """Returns the visual width of some text.

    Args:
        text: The text to test for. Spans are faster to query, as they don't need to
            rely on regex for the calculation.
    """

    if isinstance(text, Span):
        return len(text.text)

    return len(RE_ANSI.sub("", text))


class ColorSpace(Enum):
    """The color space supported by the terminal."""

    NO_COLOR = "no_color"
    """Set by the `$NO_COLOR` shell variable; convert all colors to greyscale."""

    STANDARD = "standard"
    """Only the 16 standard colors are supported."""

    EIGHT_BIT = "eight_bit"
    """256 colors are supported."""

    TRUE_COLOR = "true_color"
    """Full RGB color support is available."""


def get_default_color(
    layer: Literal["10", "11"], stream: TextIO = sys.stdout
) -> str:  # no-cov
    """Gets the default fore or back color for the terminal attached to the stream.

    Args:
        layer: The color layer. 10 for foreground color, 11 for background.
        stream: The stream to write the query to. Uses `sys.stdout` by default.

    Return:
        A hexadecimal triplet with the format `rrggbb`. Note that it doesn't include
        a leading hash.
    """

    if not sys.stdin.isatty():
        return DEFAULT_COLOR_DEFAULTS[layer]

    stream.flush()
    stream.write(f"\x1b]{layer};?\007")
    stream.flush()

    reply = getch()

    mtch = RE_PALETTE_REPLY.match(reply)
    if mtch is None:
        return DEFAULT_COLOR_DEFAULTS[layer]

    _, red, green, blue = mtch.groups()

    rgb: list[str] = []
    for part in (red, green, blue):
        rgb.append(part[:2])

    return "".join(rgb)


def get_color_space() -> ColorSpace:
    """Gets the maximum supported color system supported by the shell environment.

    Returns:
        The highest-supported color system in the terminal. If `$NO_COLOR` is set,
        `ColorSpace.NO_COLOR` will always be returned.
    """

    shell_sys = os.getenv("SLATE_COLORSYS")
    if shell_sys is not None:
        return ColorSpace(shell_sys.lower())

    if os.getenv("NO_COLOR") is not None:
        return ColorSpace.NO_COLOR

    term = os.getenv("TERM", "")
    color_term = os.getenv("COLORTERM", "").strip().lower()

    if color_term == "":
        color_term = term.split("xterm-")[-1]

    if color_term in ["24bit", "truecolor"]:
        return ColorSpace.TRUE_COLOR

    if color_term == "256color":
        return ColorSpace.EIGHT_BIT

    return ColorSpace.STANDARD


def parse_mouse_event(code: str) -> str | None:
    """Parses a mouse event.

    Args:
        code: The event sequence sent by the terminal.

    Returns:
        None if the code cannot be parsed as a mouse event, otherwise
        a string with the format:

            mouse:{event_name}@{event_x};{event_y}
    """

    if code == "\x1b" or code.count(";") != 2:
        return None

    sequence = code.lstrip("\x1b[<")
    event, posx, posy_pressed = sequence.split(";")

    posy = posy_pressed[:-1]
    pressed = posy_pressed[-1] == "M"

    event_name = MOUSE_EVENTS[event]

    if not pressed:
        event_name = event_name.replace("click", "release")

    return f"mouse:{event_name}@{posx};{posy}"


def _is_ready(file: IO[AnyStr]) -> bool:  # no-cov
    """Determines if IO object is reading to read.

    Args:
        file: An IO object of any type.

    Returns:
        A boolean describing whether the object has unread
        content.
    """

    result = select([file], [], [], 0.0)
    return len(result[0]) > 0


@contextmanager
def timeout(duration: float) -> Generator[None, None, None]:  # no-cov
    """Allows context to run for a certain amount of time, quits it once it's up.

    Note that this should never be run on Windows, as the required signals are not
    present. Whenever this function is run, there should be a preliminary OS check,
    to avoid running into issues on unsupported machines.
    """

    class TimeoutException(Exception):
        """Raised when an action has timed out."""

    def _raise_timeout(sig: int, frame: Any) -> None:
        raise TimeoutException("The action has timed out.")

    try:
        # set the timeout handler
        signal.signal(signal.SIGALRM, _raise_timeout)
        signal.setitimer(signal.ITIMER_REAL, duration)
        yield

    except TimeoutException:
        pass

    finally:
        signal.alarm(0)


def feed(text: str) -> None:
    """Feeds some text to be read by `getch`.

    This can be used to manually "interrupt" an ongoing getch call.
    """

    feeder_stream.write(text)
    feeder_stream.seek(0)


def _getch_posix(  # pylint: disable=used-before-assignment
    stream: TextIO = sys.stdin,
) -> str:  # no-cov
    """Implementation for getting characters on POSIX systems.

    Args:
        stream: The stream to read from. Defaults to `sys.stdin`.

    Returns:
        The maximum-length sequence of characters that could be read.
    """

    # TODO: Both of these should be proper module-level functions to aviod
    #       constant redefiniton.
    if stream.encoding is not None:
        decode = getincrementaldecoder(stream.encoding)().decode

    else:

        def decode(item: str) -> str:
            return item

    def _read(count: int) -> str:
        """Reads `count` elements of the stream."""

        buff = ""

        while len(buff) < count:
            char = os.read(stream.fileno(), 1)

            try:
                buff += decode(char)
            except UnicodeDecodeError:
                buff += str(char)

        return buff

    if fed_content := feeder_stream.getvalue():
        feeder_stream.truncate(0)
        feeder_stream.seek(0)

        return fed_content

    descriptor = stream.fileno()
    old_settings = termios.tcgetattr(descriptor)
    tty.setcbreak(descriptor)

    buff = ""

    try:
        buff += _read(1)

        while _is_ready(stream):
            buff += _read(1)

    finally:
        # reset terminal state, set echo on
        termios.tcsetattr(descriptor, termios.TCSADRAIN, old_settings)

    return buff


def _getch_nt() -> str:  # no-cov
    """Implementation for getting characters on NT systems.

    Returns:
        The maximum-length sequence of characters that could be read.
    """

    def _ensure_str(string: AnyStr) -> str:
        """Ensures return value is always a `str` (not `bytes`)."""

        if isinstance(string, bytes):
            return string.decode("utf-8")

        return string

    # We need to type: ignore these on non-windows machines,
    # as the library does not exist.

    # Return empty string if there is no input to get
    if not msvcrt.kbhit():  # type: ignore
        return ""

    char = msvcrt.getch()  # type: ignore
    if char == b"\xe0":
        char = "\x1b"

    buff = _ensure_str(char)

    while msvcrt.kbhit():  # type: ignore
        char = msvcrt.getch()  # type: ignore
        buff += _ensure_str(char)

    return buff


def getch(stream: TextIO = sys.stdin, raw: bool = False) -> str:  # no-cov
    """Gets characters from the stream, without blocking.

    The implementation is different on POSIX and NT systems, and this method
    always selects the correct one.

    Args:
        stream: The stream to read from. Defaults to `sys.stdin`. Note that this is
            not used on Windows, as the `msvcrt.getch` function does not support
            alternate streams.
        raw: If set, the returned string will not be converted to its canonical name,
            e.g. '\\x1b[D' -> 'left' or '\\x01' -> 'ctrl-a'.

    Returns:
        The longest sequence of characters that could be read from the stream.
    """

    if not stream.isatty():
        return ""

    if os.name == "nt":
        key = _getch_nt()

        if raw:
            return key

        return NT_KEY_NAMES.get(key, key)

    # POSIX interrupts on ctrl-c, so we 'emulate' the input when `KeyboardInterrupt`
    # is raised.
    try:
        key = _getch_posix(stream)

    except KeyboardInterrupt:
        key = chr(3)

    if raw:
        return key

    if event := parse_mouse_event("\x1b" + key.split("\x1b")[-1]):
        return event

    return POSIX_KEY_NAMES.get(key, key)


def getch_timeout(
    duration: float,
    default: str | None = None,
    stream: TextIO = sys.stdin,
    raw: bool = False,
) -> str:  # no-cov
    """Calls `getch` with a system timeout.

    Note that this on Windows this will call `getch` normally, as `SIGALRM` is not
    supported on those systems.

    Args:
        duration: The timeout's length, in seconds.
        default: What to return if no input is given within the duration.
        stream: The stream to read from. Defaults to `sys.stdin`. Note that this is
            not used on Windows, as the `msvcrt.getch` function does not support
            alternate streams.
        raw: If set, the returned string will not be converted to its canonical name,
            e.g. '\\x1b[D' -> 'left' or '\\x01' -> 'ctrl-a'.

    Returns:
        The result of `getch` if input was given before the timeout,
        otherwise `default`.
    """

    # TODO: Potentially look into a Thread-based solution here.
    if os.name == "nt":
        return getch(stream=stream, raw=raw)

    with timeout(duration):
        return getch(stream=stream, raw=raw)

    return default


def set_echo(value: bool = True) -> None:  # no-cov
    """Sets the terminal's ECHO flag to the given value.

    Currently not supported on windows.
    """

    # TODO: Figure out windows support.
    if os.name == "nt":
        return

    # TODO: This is possible with the termios module.
    os.system("stty " + ("echo" if value else "-echo"))
