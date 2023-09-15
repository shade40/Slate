from time import sleep

from slate import Span, terminal, color


def normalize(val: float, limit: int) -> int:
    return int(val / limit * 256)


def print_uv(size: tuple[int, int]) -> None:
    width, height = size

    for x in range(width):
        for y in range(height):
            col1 = color(
                (
                    normalize(x, width),
                    normalize(y, height),
                    0,
                )
            ).as_background()

            col2 = color(
                (
                    normalize(x, width),
                    normalize(y + 0.5, height),
                    0,
                )
            )

            terminal.write(Span("▄", foreground=col2, background=col1), cursor=(x, y))

    terminal.draw(redraw=True)


if __name__ == "__main__":
    # Add the printer method as a listener to the terminal's resize event, so it gets
    # reprinted every time we resize.
    terminal.on_resize += print_uv

    with terminal.alt_buffer(), terminal.no_echo():
        print_uv(terminal.size)

        while True:
            # Resize is detected manually, so we need to query for the size.
            _ = terminal.size

            terminal.draw()
            sleep(1 / 60)
