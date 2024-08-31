from slate import Span, terminal, getch, set_echo


def main() -> None:
    with terminal.no_echo(), terminal.alt_buffer(), terminal.report_mouse():
        while key := str(getch()):
            if key == "ctrl-c":
                break

            if key == "c":
                terminal.clear()
                terminal.draw(redraw=True)

            if not key.startswith("mouse:"):
                terminal.write(f" Keyboard: {key!r} ", cursor=(0, 0))

            else:
                terminal.write(f" Mouse: {key!r} ", cursor=(0, 1))

                coord_part = key.split("@")[-1]
                coords = tuple(int(x) - 1 for x in coord_part.split(";"))

                terminal.write("X", cursor=coords)

            terminal.draw()


if __name__ == "__main__":
    main()
