import asyncio
from typing import Dict, List


class DemoPubsub:
    """
    An implementation of the blog_app.events.protocols.Pubsub protocol
    using in-memory asynchronous queues.

    This is meant as a demo of how the Pubsub protocol can be used to
    generate change update subscriptions. Internal implemention is not
    efficient.
    """

    def __init__(self):
        self.subscriptions: Dict[str, List[asyncio.Queue[bytes]]] = {}

    async def subscribe(self, topic: str):
        queue = asyncio.Queue[bytes]()
        self.subscriptions.setdefault(topic, []).append(queue)

        try:
            while True:
                data = await queue.get()
                yield data
                queue.task_done()
        finally:
            self.subscriptions[topic].remove(queue)

    async def publish(self, topic: str, data: bytes):
        subscribers = self.subscriptions.get(topic, [])
        await asyncio.gather(*(sub.put(data) for sub in subscribers))

    async def dispose(self):
        ...
        # not needed; no open resources are held
