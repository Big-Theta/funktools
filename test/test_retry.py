import asyncio
import inspect

import pytest

import funktools

module = inspect.getmodule(funktools.Retry)


@pytest.fixture(autouse=True)
def event_loop() -> asyncio.AbstractEventLoop:
    """All async tests execute eagerly.

    Upon task creation return, we can be sure that the task has gotten to a point that it is either blocked or done.
    """

    eager_loop = asyncio.new_event_loop()
    eager_loop.set_task_factory(asyncio.eager_task_factory)
    yield eager_loop
    eager_loop.close()


@pytest.mark.asyncio
async def test_one_retry() -> None:
    call_count = 0

    @funktools.Retry(n=1)
    async def foo():
        nonlocal call_count
        call_count += 1
        raise Exception()

    try:
        await foo()
    except Exception:  # noqa
        ...

    assert call_count == 2
