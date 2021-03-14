from dataclasses import dataclass
from typing import Any, Optional

from strawberry.dataloader import DataLoader

from blog_app.core.helpers import Loader
from blog_app.core.model import ModelMap
from blog_app.core.protocols import AppRequest, PostContext
from .types import Post


@dataclass
class Context:
    loader: Loader[Post]

    @property
    def dataloader(self) -> DataLoader[int, Optional[Post]]:
        return self.loader.dataloader


async def build_post_context(engine: Any, table_map: ModelMap) -> PostContext:
    loader = Loader(constructor=Post, engine=engine, table=table_map["post"])
    return Context(loader=loader)