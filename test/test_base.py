import asyncio
import typing

import pytest

import funktools._base  # noqa


@pytest.fixture(autouse=True)
def event_loop() -> asyncio.AbstractEventLoop:
    """All async tests execute eagerly.

    Upon task creation return, we can be sure that the task has gotten to a point that it is either blocked or done.
    """

    eager_loop = asyncio.new_event_loop()
    eager_loop.set_task_factory(asyncio.eager_task_factory)
    yield eager_loop
    eager_loop.close()


def test_base() -> None:
    @funktools._base.Decorator()
    def foo():
        ...

    foo()


def test_key() -> None:
    @funktools._base.Decorator()
    def foo():
        ...

    assert foo.register_key == (*__name__.split('.'), test_key.__name__, foo.__name__)


def test_register() -> None:
    @funktools._base.Decorator()
    def foo():
        ...

    assert foo.register_key in funktools._base.Decorator.register.decorateds
    assert foo.register_key in funktools._base.Decorator.register.links


@pytest.mark.asyncio
async def test_async_method() -> None:

    class Foo:

        @funktools._base.Decorator()
        async def bar(self, v):
            return locals()

    assert await (foo := Foo()).bar(42) == {'self': foo, 'v': 42}


def test_multi_method() -> None:

    class Foo:

        @funktools._base.Decorator()
        def bar(self, v):
            return locals()

    assert (foo := Foo()).bar(42) == {'self': foo, 'v': 42}


@pytest.mark.asyncio
async def test_async_classmethod() -> None:

    class Foo:

        @classmethod
        @funktools._base.Decorator()
        async def bar(cls, v):
            return locals()

    assert await Foo().bar(42) == {'cls': Foo, 'v': 42}


def test_multi_classmethod() -> None:

    class Foo:

        @classmethod
        @funktools._base.Decorator()
        def bar(cls, v):
            return locals()

    assert Foo().bar(42) == {'cls': Foo, 'v': 42}


@pytest.mark.asyncio
async def test_async_staticmethod() -> None:

    class Foo:
        v: typing.ClassVar[int]

        @staticmethod
        @funktools._base.Decorator()
        async def bar(v):
            return locals()

    assert await Foo.bar(42) == {'v': 42}


def test_multi_staticmethod() -> None:

    class Foo:

        @staticmethod
        @funktools._base.Decorator()
        def bar(v):
            return locals()

    assert Foo.bar(42) == {'v': 42}
