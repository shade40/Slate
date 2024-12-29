"""The basic Event class used by the rest of the library."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TypeVar, Generic

__all__ = [
    "Event",
    "CallbackError",
]


class CallbackError(Exception):
    """Raised when something went wrong with an event's callback"""


T = TypeVar("T")


@dataclass
class Event(Generic[T]):
    """An emittable event.

    Construct an event and store it in a variable to have a reference for it. Then, you
    can `+=` callback handlers onto it, and call the event object with data to notify
    all of the callbacks.
    """

    name: str

    _listeners: list[Callable[[T], bool]] = field(default_factory=list)

    def __bool__(self) -> bool:
        """Returns whether this event has any listeners."""

        return len(self._listeners) > 0

    def __iadd__(self, callback: Callable[[T], bool]) -> Event[T]:
        if not callable(callback):
            raise ValueError(f"Invalid type for callback: {callback}")

        self.append(callback)

        return self

    def __call__(self, data: T) -> bool:
        """Emits the event to all listeners.

        Args:
            data: The content of the event.

        Returns:
            Whether any callbacks returned True.
        """

        output = False

        for callback in self._listeners:
            try:
                output |= callback(data) or True

            except Exception as exc:
                raise CallbackError(
                    f"Error executing {self.name!r} callback {callback!r}."
                ) from exc

        return output

    def append(self, callback: Callable[[T], bool]) -> None:
        """Adds a new listener."""

        self._listeners.append(callback)

    def clear(self) -> None:
        """Removes all listeners from th event."""

        self._listeners.clear()
