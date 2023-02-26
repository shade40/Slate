from __future__ import annotations

from typing import Any, Callable

from dataclasses import dataclass, field


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

    _listeners: list[Callable[[Any], Any]] = field(default_factory=list)

    def __iadd__(self, callback: Any) -> Event:
        if not callable(callback):
            raise ValueError(f"Invalid type for callback: {callback}")

        self._listeners.append(callback)

        return self

    def __call__(self, data: Any) -> int:
        """Emits the event to all listeners.

        Args:
            data: The content of the event.

        Returns:
            The amount of listeners that were notified.
        """

        for callback in self._listeners:
            try:
                callback(data)
            except Exception as exc:
                raise CallbackError(f"Error executing callback {callback!r}.") from exc

        return len(self._listeners)
