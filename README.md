![slate](https://singlecolorimage.com/get/717E8D/1600x200)

## Slate

A powerful terminal management library.

```
pip install sh40-slate
```

![rule](https://singlecolorimage.com/get/717E8D/1600x3)

### Purpose

`Slate` handles most of the interactions one might be expected to
do while writing a UI application for terminals (TUI). It does so
in a simple to understand, Pythonic manner, and uses a simple
synchronous API to allow for maximum compatibility with existing
codebases.

![rule](https://singlecolorimage.com/get/717E8D/1600x3)

### Feature highlights

#### Screen API

Under the hood, `Slate`'s terminal objects each have a `Screen`.
This screen is used for creating fast diffs of the display state
between renders, allowing you to draw _only_ the parts that changed.

Anyone who's worked with terminals before knows their rendering
is almost always the primary bottleneck of any application. They
are surprisingly awful at rendering a full-screen's result,
_especially_ when clearing the display beforehand. Many applications
result to hand-crafted update systems that only redraw the widgets
that change, but that can still be quite intensive based on the
size and content of each.

`Slate` handles cell-level diffing without you ever having to
think about it. You just draw content to the terminal, and we will
keep track of all the changes to display on the next draw, with
practically 0 performance hit.

```python
import time
from random import randint

from slate import terminal, Span, Color

# Hide the terminal's cursor
terminal.show_cursor(False)

content = [
    Span(
        "X" * terminal.width,
        bold=True,
        foreground=Color.black().lighten(2),
        background=Color.black(is_background=True).lighten(1),
    )
    for _ in range(terminal.height)
]

# Use an alt buffer to keep the pre-run terminal state intact
with terminal.alt_buffer():
    for line in content:
        terminal.write(content)

    terminal.draw()

    # Draw a '0' to a random spot on the screen, 60 times a second
    #
    # This type of operation is really taxing on terminals (especially old ones,
    # like Terminal.app) as it generally is done by redrawing the entire screen.
    # That's no longer gonna be a problem for us.
    while True:
        cursor = (randint(0, terminal.width - 1), randint(0, terminal.height - 1))

        # Make sure no more than 1 cell changes; a sanity check for the most part,
        # as this setup guarantees it.
        assert terminal.write("0", cursor=cursor) <= 1

        terminal.draw()
        time.sleep(1 / 60)
```

#### Terminal's smart cursor

If you paid attention, you might have noticed that we never moved the terminal's cursor
while drawing the initial lines of content. This is because the terminal will always track
and move its own cursor when written to, so it knows when it ran out of space and needs
to move to a new line.

```python
from slate import terminal

print(terminal.cursor)  # (0, 0)

terminal.write("1")
print(terminal.cursor)  # (1, 0)
```

It will even wrap while writing!

```python
from slate import terminal, getch

# It will even wrap while writing!
terminal.write("#" * (terminal.width - 5))
terminal.write("This is long, but it will wrap around to the next line.")
terminal.draw()

getch() # Wait for input so the shell prompt doesn't slide things out of view
```

#### Sophisticated color tools

You might have noticed the usage of the lighten and darken API for colors above. These
are amongst the many tools we provide for working with colors, which also include blending,
generating W3C guidelines compliant contrast colors (white for dark colors, black for light
ones), generating entire 4-color palettes with multiple of the most commonly used strategies,
and more.

Best part; **it works everywhere**. Colors get translated to the best approximation the current
terminal can display, so you don't have to worry about things looking completely wonky without
true color support. Most terminals (at least ones you should be using / targeting) have true
color support nowadays, but our approximations will be _good enough_ to use on older ones as
well.

We also have advanced support for the [NO_COLOR](https://no-color.org/) initiative, but instead
of completely stripping the semantic information colors can convey, we translate each color
to a greyscale value that matches with the _perceived_ [lightness](https://en.wikipedia.org/wiki/Lightness),
keeping the application informative.

<p align=center>
    <img src="https://github.com/shade40/slate/blob/main/assets/color_grids.png?raw=true" alt="Color grid example">
</p>

### Documentation

Once the library gets to a settled state (near 1.0), documentation will be hosted both online and as a celx
application. Until then peep the `examples` folder, or check out some of the references by using
`python3 -m pydoc <name>`.

### See also

This library is mostly supposed to _power_ some higher level tools, so using it raw might
not be ideal. Thankfully, we have two projects that can help with that:

- [Zenith](https://github.com/shade40/zenith): A markup language with palette generation, built
    on `Slate`'s `Span` and `Color` primitives.
- [Celadon](https://github.com/shade40/celadon): A TUI library that uses `Slate`'s `Terminal` to
    handle _all_ terminal-interfacing.
- [celx](https://github.com/shade40/celx): A hypermedia-driven TUI framework built on top of `Celadon`.
