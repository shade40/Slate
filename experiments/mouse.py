from undertone import Span, Terminal, getch, set_echo

if __name__ == "__main__":
    term = Terminal()

    try:
        set_echo(False)

        with term.alt_buffer(), term.report_mouse():
            while key := getch():
                if key == chr(3):
                    break

                if key == "c":
                    term.clear()
                    term.draw(redraw=True)

                if not key.startswith("mouse:"):
                    term.write(f" Pressed: {key!r} ", cursor=(0, 0))
                    term.draw()
                    continue

                term.write(f" Mouse: {key!r} ", cursor=(0, 1))

                # This drawing method is pretty ugly, but it works.
                coords = tuple(int(x) for x in key.split("@")[-1].split(";"))
                coords = coords[0] - 1, coords[1] - 1

                term.write("X", cursor=coords)

                term.draw()

    finally:
        set_echo(True)
