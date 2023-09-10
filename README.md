![slate](https://singlecolorimage.com/get/717E8D/1600x200)

## Slate

A powerful terminal management library.

```
pip install sh40-slate
```

![rule](https://singlecolorimage.com/get/717E8D/1600x5)

### Purpose

`Slate` handles most of the interactions one might be expected to
do while writing a UI application for terminals (TUI). It does so
in a simple to understand, Pythonic manner, and uses a simple
synchronous API to allow for maximum compatibility with existing
codebases.

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

with terminal.alt_buffer():
    for line in content:
        terminal.write(content)

    terminal.draw()

    while True:
        cursor = (randint(0, terminal.width - 1), randint(0, terminal.height - 1))

        # Make sure no more than 1 cell changes; a sanity check for the most part,
        # as this setup guarantees it.
        assert terminal.write("0", cursor=cursor) <= 1

        terminal.draw()
        time.sleep(1 / 60)
```
