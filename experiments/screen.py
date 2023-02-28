import time
from random import randint

from undertone import Span, Terminal, getch_timeout, set_echo
from undertone.screen import Screen

from .markup import styled_from_markup as markup
from .screen_resize import redraw

if __name__ == "__main__":
    term = Terminal()

    def redraw(size: tuple[int, int]) -> None:
        term.draw(redraw=True)

    term.on_resize += redraw

    writes = 0
    draws = 0

    write_time = 0
    draw_time = 0

    try:
        set_echo(False)

        with term.alt_buffer():
            while True:
                changes = 0
                width, height = term.size

                start = time.perf_counter_ns()
                for _ in range(1000):
                    position = randint(0, width - 1), randint(0, height - 2)
                    color1 = randint(0, 255)
                    color2 = randint(0, 255)

                    changes += term.write(
                        markup(f"[@{color1} {color2}]▄"), cursor=position
                    )

                write_time += time.perf_counter_ns() - start
                writes += 1

                term.write(f" Changes: {changes} ", cursor=(0, 0))

                start = time.perf_counter_ns()
                term.draw()

                draw_time += time.perf_counter_ns() - start
                draws += 1

                time.sleep(1 / 60)

    finally:
        set_echo(True)

        print(f"# of writes: {writes}")
        print(f"# of draws: {draws}")

        if writes + draws > 2:
            print(f"mean write time: {write_time / writes}")
            print(f"mean draw time: {draw_time / draws}")
