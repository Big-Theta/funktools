from __future__ import annotations

import abc
import asyncio
import collections
import concurrent.futures
import dataclasses
import sys
import threading
import typing

from . import _base


type Expire = float
type Key = typing.Hashable
type GenerateKey[** Params] = typing.Callable[Params, Key]


@dataclasses.dataclass(frozen=True, kw_only=True)
class EnterContext[** Params, Return](
    _base.EnterContext[Params, Return],
    abc.ABC,
):
    exit_context_by_key: collections.OrderedDict[Key, ExitContext[Params, Return]] = dataclasses.field(
        default_factory=collections.OrderedDict
    )
    generate_key: GenerateKey[Params]
    size: int

    @abc.abstractmethod
    def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs
    ) -> (
        (ExitContext[Params, Return], _base.EnterContext[Params, Return])
        | asyncio.Future[Return]
        | concurrent.futures.Future[Return]
    ):
        key = self.generate_key(*args, **kwargs)
        while self.size < len(self.exit_context_by_key):
            self.exit_context_by_key.popitem(last=False)
        if (exit_context := self.exit_context_by_key.pop(key, None)) is None:
            exit_context = self.exit_context_by_key[key] = self.exit_context_t()
            return exit_context, self.next_enter_context

        self.exit_context_by_key[key] = exit_context
        return exit_context.future

    def __get__(self, instance: _base.Instance, owner) -> EnterContext[Params, Return]:
        with self.instance_lock:
            if (enter_context := self.enter_context_by_instance.get(instance)) is None:
                enter_context = self.enter_context_by_instance[instance] = dataclasses.replace(
                    self,
                    next_enter_context=self.next_enter_context.__get__(instance, owner),
                    exit_context_by_key=collections.OrderedDict(),
                    instance=instance,
                )
            return enter_context


@dataclasses.dataclass(frozen=True, kw_only=True)
class ExitContext[** Params, Return](
    _base.ExitContext[Params, Return],
    abc.ABC,
):
    future: asyncio.Future[Return] | concurrent.futures.Future[Return]

    @abc.abstractmethod
    def __call__(self, result: _base.Raise | Return) -> Return:
        if isinstance(result, _base.Raise):
            self.future.set_exception(result.exc_val)
        else:
            self.future.set_result(result)
        return result


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncEnterContext[** Params, Return](
    EnterContext[Params, Return],
    _base.AsyncEnterContext[Params, Return],
):
    lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)

    async def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs
    ) -> (AsyncExitContext[Params, Return], _base.AsyncEnterContext[Params, Return]) | Return:
        async with self.lock:
            result = super().__call__(*args, **kwargs)

        # FIXME: what if someone explicitly returns a Future from their own code? We don't want to await it.
        if isinstance(result, asyncio.Future):
            result = await result

        return result


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiEnterContext[** Params, Return](
    EnterContext[Params, Return],
    _base.MultiEnterContext[Params, Return],
):
    lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)

    def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs
    ) -> (MultiExitContext[Params, Return], _base.MultiEnterContext[Params, Return]) | Return:
        with self.lock:
            result = super().__call__(*args, **kwargs)

        if isinstance(result, concurrent.futures.Future):
            result = result.result()

        return result


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncExitContext[** Params, Return](
    ExitContext[Params, Return],
    _base.AsyncExitContext[Params, Return],
):
    future: asyncio.Future = dataclasses.field(default_factory=asyncio.Future)

    async def __call__(self, result: _base.Raise | Return) -> Return:
        return super().__call__(result)


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiExitContext[** Params, Return](
    ExitContext[Params, Return],
    _base.MultiExitContext[Params, Return],
):
    future: concurrent.futures.Future = dataclasses.field(default_factory=concurrent.futures.Future)

    def __call__(self, result: _base.Raise | Return) -> Return:
        return super().__call__(result)


@dataclasses.dataclass(frozen=True, kw_only=True)
class Decorator[** Params, Return](
    _base.Decorator[Params, Return],
):
    size: int = sys.maxsize
    generate_key: GenerateKey[Params] = lambda *args, **kwargs: (tuple(args), tuple(sorted([*kwargs.items()])))

    register: typing.ClassVar[_base.Register] = _base.Register()

    def __call__(
        self,
        decoratee: _base.Decoratee[Params, Return] | _base.Decorated[Params, Return],
        /,
    ) -> _base.Decorated[Params, Return]:
        decoratee = super().__call__(decoratee)

        match decoratee:
            case _base.AsyncDecorated():
                enter_context_t = AsyncEnterContext
            case _base.MultiDecorated():
                enter_context_t = MultiEnterContext
            case _: assert False, 'Unreachable'  # pragma: no cover

        decorated = self.register.decorateds[decoratee.register_key] = dataclasses.replace(
            decoratee,
            enter_context=enter_context_t(
                generate_key=self.generate_key,
                next_enter_context=decoratee.enter_context,
                size=self.size,
            ),
        )

        return decorated
