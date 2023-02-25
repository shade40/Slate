from typing import Any, Callable

from dataclasses import dataclass, field


class CallbackError(Exception):
    """Raised when something went wrong with an event's callback"""


@dataclass
class Event:
    name: str
    bound: object

    _listeners: list[Callable[[Any], Any]] = field(default_factory=list)

    def __iadd__(self, callback: Any) -> None:
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
