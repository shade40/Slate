import os
from argparse import ArgumentParser

from . import getch, Span, terminal, color, Color
from .__about__ import __version__

def run_getch() -> None:
    print(Span("Waiting for input...", dim=True), end=" ", flush=True)
    key = getch()
    print("|".join(key.possible_values))

def run_size() -> None:
    print(" x ".join(map(str, terminal.size)))

def run_debug() -> None:
    rows = [
        ("Environment:", ""),
        ("$TERM", os.getenv("TERM", "-")),
        ("$COLORTERM", os.getenv("COLORTERM", "-")),
        ("$NO_COLOR", os.getenv("NO_COLOR", "-")),
        ("$SLATE_COLORSYS", os.getenv("SLATE_COLORSYS", "-")),
        ("Terminal state:", ""),
        ("size", "x".join(map(str, terminal.size))),
        ("colorspace", str(terminal.color_space)),
        ("synchronized update support", str(terminal.supports_synchronized_update)),
        ("foreground color", terminal.foreground_color.hex),
        ("background color", terminal.background_color.hex),
    ]
    
    max_left = max(len(row[0]) for row in rows) + 3
    max_right = max(len(row[1]) for row in rows) + 3

    buff = ""

    for left, right in rows:
        if right == "":
            if buff:
                buff += "\n"

            buff += str(Span(left, bold=True)) + "\n"
            continue

        buff += str(Span(f"{left:<{max_left}}", dim=True))

        if "ground color" in left:
            c = color(right)

            buff += (max_right - len(right)) * " " + str(
                Span(
                    right,
                    foreground=c,
                    background=c.contrast.as_background(),
                )
            )

        else:
            buff += str(Span(f"{right:>{max_right}}"))

        buff += "\n"

    print(f"\n{buff}")


def main() -> None:
    """The main entrypoint."""

    parser = ArgumentParser("slate", description="Small tools for the terminal.")
    parser.add_argument("-v", "--version", action="version", version=__version__)

    subs = parser.add_subparsers(required=True)

    subs.add_parser("getch").set_defaults(func=run_getch)
    subs.add_parser("size").set_defaults(func=run_size)
    subs.add_parser("debug").set_defaults(func=run_debug)

    args = parser.parse_args()

    command = args.func

    opts = vars(args)
    del opts["func"]

    command(**vars(args))


if __name__ == "__main__":
    main()
