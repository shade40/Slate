"""The basic Event class used by the rest of the library."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Union

EventCallback = Union[Callable[[], bool | None], Callable[[Any], bool | None]]

__all__ = [
    "Event",
    "EventCallback",
    "CallbackError",
]


class CallbackError(Exception):
    """Raised when something went wrong with an event's callback"""


@dataclass
class Event:
    """An emittable event.

    Construct an event and store it in a variable to have a reference for it. Then, you
    can `+=` callback handlers onto it, and call the event object with data to notify
    all of the callbacks.
    """

    name: str

    _listeners: list[EventCallback] = field(default_factory=list)

    def __bool__(self) -> bool:
        """Returns whether this event has any listeners."""

        return len(self._listeners) > 0

    def __iadd__(self, callback: EventCallback) -> Event:
        if not callable(callback):
            raise ValueError(f"Invalid type for callback: {callback}")

        self._listeners.append(callback)

        return self

    def __call__(self, data: Any | None = None) -> int:
        """Emits the event to all listeners.

        Args:
            data: The content of the event.

        Returns:
            The amount of listeners that were notified.
        """

        output = False

        for callback in self._listeners:
            try:
                try:
                    output |= callback(data) or False
                except TypeError:
                    output |= callback() or False  # type: ignore

            except Exception as exc:
                raise CallbackError(f"Error executing callback {callback!r}.") from exc

        return len(self._listeners)

    def clear(self) -> None:
        """Removes all listeners from th event."""

        self._listeners.clear()
