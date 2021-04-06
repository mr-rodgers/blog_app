import gc
import time
from asyncio.base_events import BaseEventLoop
from unittest import mock

import pytest

from blog_app import evts
from blog_app.events.demo_pubsub import DemoPubsub
from .conftest import GraphQLClient


class TestPubsub(DemoPubsub):
    """Pubsub with extra methods for testing"""

    @property
    def active_subscriptions(self):
        return [sub for subs in self.subscriptions.values() for sub in subs]


@pytest.fixture
def pubsub():
    old_pubsub = evts.pubsub
    evts.pubsub = TestPubsub()
    yield evts.pubsub
    evts.pubsub = old_pubsub


@pytest.fixture
def tick_until(post, client):
    # A fixture function which delays the current thread until
    # garbage collector dependent conditions are met, or a timeout
    # elapses.

    def tick():
        time.sleep(0)
        gc.collect()

    def _check_for_condition(func, timeout=5):
        start_time = time.time()
        elapsed = time.time() - start_time

        while elapsed < timeout and not func():
            tick()
            elapsed = time.time() - start_time

    return _check_for_condition


@pytest.fixture
def loop_tick(post, client):
    """A function that runs asynchronous code on the blog app server."""
    # normally, this will happen automatically since the event loop
    # runs indefinitely on the server. However, during testing the
    # event loop is constrained to run only during requests from the
    # test client. Therefore asynchronous tasks that occur outside of
    # a request will not run since the event loop will be paused, so
    # we need a function to run those async tasks
    import gc


def test_watch_post(client: GraphQLClient, post, post_factory, comment_fetcher):
    with client.subscribe(
        """
        subscription watchPost($postId: Int!) {
            watchPost(id: $postId) {
                __typename
                ... on PostUpdatedEvent {
                    id
                    content
                }
                ... on CommentAddedEvent {
                    id
                    content
                }
            }
        }
        """,
        variables={"postId": post.id},
    ) as subscription:
        new_content = post_factory.build().content
        result = client.execute(
            """
            mutation updatePost($postId: Int!, $content: String!) {
                updatePost(id: $postId, content: $content) {
                    __typename
                }
            }
            """,
            variables={"postId": post.id, "content": new_content},
            access_token=post.author.access_token,
        )
        assert result.get("errors") is None
        data = next(subscription)["data"]

        assert data["watchPost"]["id"] == post.id
        assert data["watchPost"]["content"] == new_content

        comment_content = post_factory.build().content
        result = client.execute(
            """
            mutation addComment($postId: Int!, $content: String!) {
                addComment(postId: $postId, content: $content) {
                    __typename
                }
            }
            """,
            variables={"postId": post.id, "content": comment_content},
            access_token=post.author.access_token,
        )
        assert result.get("errors") is None
        data = next(subscription)
        data = data["data"]

        assert data["watchPost"]["__typename"] == "CommentAddedEvent"
        # assert data["watchPost"]["id"] != post.id

        assert comment_fetcher.fetch(data["watchPost"]["id"]).content == comment_content


def test_subscription_cleanup_on_unsubscribe(
    client: GraphQLClient, pubsub: TestPubsub, post, tick_until
):
    assert not pubsub.active_subscriptions
    with client.subscribe(
        """
        subscription watchPost($postId: Int!) {
            watchPost(id: $postId) {
                __typename
                ... on PostUpdatedEvent {
                    id
                    content
                }
                ... on CommentAddedEvent {
                    id
                    content
                }
            }
        }
        """,
        variables={"postId": post.id},
    ) as subscription:
        tick_until(lambda: pubsub.active_subscriptions)
        assert pubsub.active_subscriptions

        subscription.unsubscribe()

    # due to how Python async generators are finalized, we have to
    # wait on the garbage collector to call the finally: block from
    # the pubsub subscription (cleanup), which occurs at some indeterminate point
    # after the async generator is discarded (there is currently no mechanism to signal
    # cleanup of the generator, once iteration has begun).
    # tick_until() essentially blocks the thread until this has completed,
    # eagerly and repeatedly triggering garbage collection in the meantime.
    tick_until(lambda: not pubsub.active_subscriptions)
    assert not pubsub.active_subscriptions
