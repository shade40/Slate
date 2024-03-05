import pytest

from slate.event import CallbackError, Event


def test_event_emit():
    def _callback(data: str) -> bool:
        assert data == "this is a test"

        return True

    test = Event("Test 1")
    test += _callback

    test("this is a test")


def test_event_bad_callback():
    test = Event("Test 2")

    with pytest.raises(ValueError):
        test += "this won't work"


def test_event_callback_error():
    def _bad_callback(data: str):
        1 / 0

    test = Event("Test 3")

    test += _bad_callback

    with pytest.raises(CallbackError):
        test("whatever")
