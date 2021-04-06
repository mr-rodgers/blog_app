from typing import AsyncIterator, List, Protocol, Dict, Union


class Pubsub(Protocol):
    """
    Used to send and receive event data over a pubsub backend.
    """

    async def publish(self, topic: str, event_data: bytes) -> None:
        ...

    def subscribe(self, topic: str) -> AsyncIterator[bytes]:
        ...

    async def dispose(self):
        ...
