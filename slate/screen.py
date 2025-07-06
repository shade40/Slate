"""The Screen class, which allows for smart overwrite-based terminal drawing."""

from __future__ import annotations

from typing import Iterable

from slate.core import RE_ANSI

from .color import Color
from .span import Span, SVG_CHAR_WIDTH, SVG_CHAR_HEIGHT


def _get_blended(
    base: Color | None,
    other: Color | None,
    is_background: bool | None = None,
    alpha_addition: float = 0.0
) -> Color | None:
    """Returns `base` blended by `other` at `other`'s alpha value."""

    if base is None and other is None:
        return None

    if base is not None and other is None:
        return base

    if other is not None and base is None:
        return other

    return base.blend(other, other.alpha+alpha_addition, is_background=is_background)  # type: ignore


class ChangeBuffer:
    """A simple class that keeps track of x, y positions of changed characters."""

    def __init__(self) -> None:
        self._data: dict[tuple[int, int], str] = {}

    def __setitem__(self, indices: tuple[int, int], value: str) -> None:
        self._data[indices] = value

    def clear(self) -> None:
        """Clears the buffer."""

        self._data.clear()

    def gather(self) -> list[tuple[tuple[int, int], str]]:
        """Gathers all changes.

        Returns:
            A list of items in the format:

                (x, y), changed_str

        """

        items: list[tuple[tuple[int, int], str]] = [*self._data.items()]
        return sorted(items, key=lambda item: (item[0][1], item[0][0]))


class Screen:
    """A matrix of cells that represents a 'screen'.

    This matrix keeps track of changes between each draw, so only the newest changes
    are written to the terminal. This helps eliminate full-screen redraws.
    """

    def __init__(
        self,
        width: int,
        height: int,
        cursor: tuple[int, int] = (0, 0),
        fillchar: str = " ",
    ) -> None:
        self._cells: list[list[tuple[str, Color | None, Color | None]]] = []
        self._change_buffer = ChangeBuffer()

        self.cursor: tuple[int, int] = cursor

        self.resize((width, height), fillchar)

    def resize(
        self, size: tuple[int, int], fillchar: str = " ", keep_original: bool = True
    ) -> None:
        """Resizes the cell matrix to a new size.

        Args:
            size: The new size.
        """

        width, height = size

        cells: list[list[tuple[str, Color | None, Color | None]]] = []
        cells_append = cells.append
        change_buffer = self._change_buffer.__setitem__

        for y in range(height):
            row: list[tuple[str, Color | None, Color | None]] = []

            for x in range(width):
                row.append((fillchar, None, None))
                change_buffer((x, y), fillchar)

            cells_append(row)

        if keep_original:
            for y, row in enumerate(self._cells):
                if y >= height:
                    break

                for x, (char, fore, back) in enumerate(row):
                    if x >= width:
                        break

                    cells[y][x] = char, fore, back

        self.width = width
        self.height = height

        self._cells = cells

    def clear(self, fillchar: str = " ") -> None:
        """Clears the screen's entire matrix.

        Args:
            fillchar: The character to fill the matrix with.
        """

        self.resize((self.width, self.height), fillchar, keep_original=False)
        self.cursor = (0, 0)

    def write(
        self,
        spans: Iterable[Span],
        cursor: tuple[int, int] | None = None,
        terminal_background: Color = Color.black(),
        force_overwrite: bool = False,
    ) -> int:
        """Writes data to the screen at the given cursor position.

        Args:
            spans: Any iterator of Span objects.
            cursor: The location of the screen to start writing at, anchored to the
                top-left. If not given, the screen's last used cursor is used.
            force_overwrite: If set, each of the characters written will be registered
                as a change.

        Returns:
            The number of cells that have been updated as a result of the write.
        """

        return self.write_bulk([(cursor, spans)], force_overwrite=force_overwrite, terminal_background=terminal_background)

    def write_bulk(
        self,
        data: list[tuple[tuple[int, int], Iterable[Span]]],
        terminal_background: Color = Color.black(),
        force_overwrite: bool = False,
    ) -> int:
        """Writes bulked data to the screen. This function culls any later-overwritten
            cell writes.

        Args:
            data: A list of tuples of:
                ((pos_x, pos_y), span_iterable)
            force_overwrite: If set, each of the characters written will be registered
                as a change.

        Returns:
            The number of cells that have been updated as a result of the write.
        """

        blank = (" ", None, terminal_background, False, False)
        write_matrix = [
            [blank] * self.width
            for _ in range(self.height)
        ]

        alpha_matrix = []

        for _ in range(self.height):
            line = []

            for _ in range(self.width):
                line.append([])

            alpha_matrix.append(line)

        for ((x, y), line) in data:
            for span in line:
                foreground, background = span.foreground, span.background
                background = background
                bg_has_alpha = background is not None and background.alpha != 1.0

                chars = span.get_characters(exclude_color=True, always_include_sequence=True)
                chars_len = len(chars)

                for i, char in enumerate(chars):
                    if self.width <= x or x < 0 or self.height <= y or y < 0:
                        break

                    if char == "\n":
                        y += 1
                        continue

                    last = i == chars_len - 1

                    next_x, next_y = x + 1, y

                    if next_x >= self.width:
                        next_y += 1
                        next_x = 0

                    final_fg = foreground
                    final_bg = background
                    final_char = char

                    if write_matrix[y][x] is not blank and bg_has_alpha:
                        alpha_matrix[y][x].append(background)
                        empty = RE_ANSI.sub("", char).strip() == ""

                        final_fg = foreground if not empty else write_matrix[y][x][1]
                        final_bg = write_matrix[y][x][2]
                        final_char = char if not empty else write_matrix[y][x][0]

                    write_matrix[y][x] = (final_char, final_fg, final_bg, last, char != final_char)

                    x, y = next_x, next_y

        changes = 0

        for y, line in enumerate(write_matrix):
            for x, cell in enumerate(line):
                if cell is blank:
                    continue

                try:
                    alpha_stack = alpha_matrix[y][x]
                except:
                    alpha_stack = {}

                char, fg, bg, last, bleedthrough = cell
                fg = fg or Color.white()
                blent = bg

                last = bg

                for i, color in enumerate(alpha_stack):
                    if color == last:
                        continue

                    last = color

                    blent = _get_blended(blent, color, alpha_addition=0.1)
                    if bleedthrough:
                        fg = _get_blended(fg, color, alpha_addition=0.1)

                if blent and blent.alpha != 1.0:
                    blent = _get_blended(terminal_background, blent, alpha_addition=0.1)

                bg = blent

                if fg is not None and fg.alpha != 1.0:
                    fg = _get_blended(fg, bg)

                new = (char, fg, bg)

                if new != self._cells[y][x]:
                    self._cells[y][x] = new

                    colors = []
                    if fg is not None:
                        colors.append(fg.ansi)
                    if bg is not None:
                        colors.append(bg.ansi)
                    color = ";".join(colors)

                    if color:
                        char = f"\x1b[{color}m{char}\x1b[0m"

                    self._change_buffer[x, y] = char

                    changes += 1

        return changes


    def render(self, origin: tuple[int, int] = (0, 0), redraw: bool = False) -> str:
        """Collects all buffered changes and returns them as a single string.

        Args:
            origin: The offset to apply to all positions.
        """

        x, y = origin

        if redraw:
            buffer = ""

            for row in self._cells:
                buffer += f"\x1b[{y};{x}H" + "".join(str(item) for item, *_ in row)
                y += 1

            self._change_buffer.clear()

            return buffer

        buffer = ""

        previous_x = None
        previous_y = None

        for ((x, y), char) in self._change_buffer.gather():
            x += origin[0]
            y += origin[1]

            if previous_x is not None and (x == previous_x + 1 and y == previous_y):
                buffer += char
            else:
                buffer += f"\x1b[{y};{x}H{char}"

            previous_x, previous_y = x, y

        self._change_buffer.clear()

        if not buffer.endswith("\x1b[0m"):
            buffer += "\x1b[0m"

        return buffer

    def export_svg_with_styles(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        font_size: int,
        origin: tuple[float, float],
        default_foreground: Color,
        default_background: Color,
        style_class_template: str = "screen__span{i}",
    ) -> tuple[str, str]:
        """Exports a whole load of SVG tags that represents our character matrix.

        Args:
            font_size: The font size within the SVG.
            origin: The origin of all the coordinates in the output.
            default_foreground: If a character doesn't have a foreground, this gets
                substituted.
            default_background: If a character doesn't have a foreground, this gets
                substituted.
            style_class_template: The template used to create classes for each unique
                style. Must contain `{i}`.

        Returns:
            The output SVG, and all the styles contained within. Note that the SVG
            here is only the body, so you need to wrap it as `<svg ...>{here}</svg>`.
            Terminal does this automatically.
        """

        def _get_svg(span: Span, x: float, y: float, i: int) -> tuple[str, str]:
            """Gets the SVG and CSS styling for any given span."""

            cls = style_class_template.format(i=i)
            css = ";\n".join(
                f"{key}:{value}" for key, value in span.get_svg_styles().items()
            )

            return (
                span.as_svg(
                    font_size=font_size,
                    default_foreground=default_foreground,
                    default_background=default_background,
                    origin=(x, y),
                    cls=cls,
                ),
                (f".{cls} {{" + css + "}\n"),
            )

        x, y = origin

        svg = ""
        stylesheet = ""

        char_width = font_size * SVG_CHAR_WIDTH
        char_height = font_size * SVG_CHAR_HEIGHT

        previous_attrs = None

        i = 0
        for row in self._cells:
            for span in Span.group([span for span, *_ in row]):
                if previous_attrs != span.attrs:
                    i += 1

                new_svg, new_style = _get_svg(span, x, y, i)
                svg += new_svg
                stylesheet += new_style

                previous_attrs = span.attrs
                x += len(span) * char_width

            y += char_height
            x = origin[0]

        return svg, stylesheet
