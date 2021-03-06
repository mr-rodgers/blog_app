import enum
from typing import TypedDict

from sqlalchemy.schema import Column, MetaData, Table, UniqueConstraint
from sqlalchemy.sql import func, text, ColumnElement

from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.types import Enum, Integer, String, Text, TIMESTAMP

from .model_helper import ModelHelper


class ReactionType(enum.Enum):
    like = "like"
    thumbs_up = "thumbs_up"
    smile = "smile"


class ModelMap(TypedDict):
    post: ModelHelper
    comment: ModelHelper
    reaction: ModelHelper


def register_tables(metadata: MetaData) -> ModelMap:
    return ModelMap(
        post=ModelHelper(
            table=Table(
                "post",
                metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column("title", String(150), nullable=False),
                Column("author_id", String(32), nullable=False, index=True),
                Column("content", Text),
                Column("created", TIMESTAMP, nullable=False, server_default=func.now()),
                Column(
                    "updated",
                    TIMESTAMP,
                    nullable=False,
                    server_default=text(
                        "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
                    ),
                ),
                mysql_engine="InnoDB",
                mysql_charset="utf8mb4",
            ),
            author_key="author_id",
            engine=metadata.bind,
        ),
        comment=ModelHelper(
            table=Table(
                "comment",
                metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column(
                    "post_id",
                    Integer,
                    ForeignKey("post.id", ondelete="CASCADE"),
                    nullable=False,
                    index=True,
                ),
                Column("author_id", String(32), nullable=False),
                Column("content", Text),
                Column("created", TIMESTAMP, nullable=False, server_default=func.now()),
                Column(
                    "updated",
                    TIMESTAMP,
                    nullable=False,
                    server_default=text(
                        "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
                    ),
                ),
                mysql_engine="InnoDB",
                mysql_charset="utf8mb4",
            ),
            author_key="author_id",
            engine=metadata.bind,
        ),
        reaction=ModelHelper(
            table=Table(
                "reaction",
                metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column(
                    "comment_id",
                    Integer,
                    ForeignKey("comment.id", ondelete="CASCADE"),
                    nullable=False,
                    index=True,
                ),
                Column("author_id", String(32), nullable=False),
                Column("reaction_type", Enum(ReactionType), nullable=False),
                Column(
                    "updated",
                    TIMESTAMP,
                    nullable=False,
                    server_default=text(
                        "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
                    ),
                ),
                UniqueConstraint("comment_id", "author_id"),
                mysql_engine="InnoDB",
                mysql_charset="utf8mb4",
            ),
            author_key="author_id",
            engine=metadata.bind,
        ),
    )


__all__ = ["ModelHelper", "ModelMap"]
