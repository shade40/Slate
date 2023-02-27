from undertone import Terminal, set_echo, Span, getch

from .markup import styled_from_markup as markup


term = Terminal()


def redraw(size: tuple[int, int]) -> None:
    term.draw(redraw=True)


if __name__ == "__main__":
    # Manually register redraw onto the event; this should be done by
    # whoever is redrawing the terminal regularly.
    term.on_resize += redraw

    with term.alt_buffer():
        width, height = term.size

        for x in range(width):
            for y in range(height):
                color1 = f"{int(x / width * 256)};{int(y / height * 256)};0"
                color2 = f"{int(x / width * 256)};{int((y + 0.5) / height * 256)};0"

                term.write(markup(f"[@{color1} {color2}]▄"), cursor=(x, y))

        while True:
            # Resize is detected manually, so we need to query for the size.
            _ = term.size

            term.draw()
