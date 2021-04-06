from typing import Optional
import pytest

from dataclasses import dataclass

from blog_app.events import Matcher


@dataclass
class FakeEventClass:
    bar: str
    foo: Optional[int] = None


@pytest.mark.parametrize(
    "matcher,payload,expected",
    [
        (
            Matcher(FakeEventClass, bar="some str"),
            {"bar": "some str"},
            FakeEventClass(bar="some str"),
        ),
        (
            Matcher(FakeEventClass, foo=10),
            {"foo": 10, "bar": "literally anything"},
            FakeEventClass(foo=10, bar="literally anything"),
        ),
        (
            Matcher(FakeEventClass, bar="some str"),
            {"bar": "wrong str"},
            None,
        ),
        # looks like a match, but required "bar" argument is
        # missing
        (Matcher(FakeEventClass, foo=10), {"foo": 10}, None),
        # match arg just not present at all
        (Matcher(FakeEventClass, foo=10), {"bar": "some str"}, None),
    ],
)
def test_matcher(matcher, payload, expected):
    assert matcher.match(payload) == expected
