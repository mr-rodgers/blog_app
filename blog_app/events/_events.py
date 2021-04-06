import aiostream.stream
import bson
import json
import logging
from dataclasses import dataclass, asdict, fields
from functools import wraps
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Generic,
    List,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
)

from blog_app.core import AppError
from .protocols import Pubsub


class EventConstructor(Protocol):
    def __init__(self, **kwargs: Union[str, int, List[str], List[int]]):
        ...


T = TypeVar("T")

EventType = TypeVar("EventType", bound=EventConstructor)


class Matcher(Generic[EventType]):
    constructor: Type[EventType]

    def __init__(self, constructor: Type[EventType], **match_args):
        self.constructor = constructor
        self.match_args = match_args

        self.required_fields = fields(self.constructor)

    def match(self, payload: dict) -> Optional[EventType]:
        for match_arg in self.match_args:
            if match_arg not in payload:
                logging.info(
                    "Match failed: key %r not found in event payload. Skipping.",
                    match_arg,
                )
                return None

            required_value = self.match_args[match_arg]
            if payload[match_arg] != required_value:
                logging.info(
                    "Match failed: key %(key)r expected %(expected)r, but got %(got)r. Skipping.",
                    dict(
                        key=match_arg, expected=required_value, got=payload[match_arg]
                    ),
                )
                return None

        kwargs = {}

        for field in self.required_fields:
            if field.name in payload:
                kwargs[field.name] = payload[field.name]

        try:
            return self.constructor(**kwargs)
        except:
            logging.error("Failed event payload: %s", json.dumps(payload))
            logging.exception(
                "Couldn't generate %(event_type)r from event payload. Skipping.",
                dict(event_type=self.constructor),
            )
            return None


@dataclass
class Events:
    pubsub: Optional[Pubsub] = None

    def track(self, mutator_func: Callable[..., Any], generating: Type):
        @wraps(mutator_func)
        async def wrapper(**kwargs):
            result = mutator_func(**kwargs)

            if isinstance(result, Awaitable):
                result = await result  # some resolvers are async.

            await self._submit_event(result, kwargs, generating)
            return result

        return wrapper

    async def stream(
        self, *matchers: Matcher[EventType]
    ) -> AsyncGenerator[EventType, None]:
        if self.pubsub is None:
            raise RuntimeError(
                "Cannot stream events without a Pubsub adaptor. Did you forget to attach one (self.pubsub)?"
            )

        async def wrap(matcher: Matcher):
            assert self.pubsub is not None
            subscription = self.pubsub.subscribe(self._get_topic(matcher.constructor))
            async for data in subscription:
                try:
                    payload = bson.loads(data)
                except:
                    logging.exception(
                        "Encountered a problem when retrieving mutation event."
                    )
                else:
                    event = matcher.match(payload)

                    if event:
                        yield event

        subscriptions = (wrap(matcher) for matcher in matchers)

        async with aiostream.stream.merge(*subscriptions).stream() as streamer:
            async for event in streamer:
                yield event

    async def _submit_event(self, result: Any, resolver_args: dict, generating: Type):
        """If a pubsub is defined, submit the given event onto it."""
        if self.pubsub is not None and not isinstance(result, AppError):
            payload = {}
            payload.update(resolver_args)
            payload.update(asdict(result))

            def generate_keys(obj: Union[dict, list], _):
                view = enumerate(obj) if isinstance(obj, list) else obj.items()
                return (key for key, val in view if isinstance(val, (int, str)))

            try:
                data = bson.dumps(payload, generate_keys)
                topic = self._get_topic(generating)
                await self.pubsub.publish(topic, data)
            except:
                logging.exception("Encountered a problem when publishing event.")

    def _get_topic(self, generating: Type):
        return f"event:{generating.__module__}.{generating.__qualname__}"
