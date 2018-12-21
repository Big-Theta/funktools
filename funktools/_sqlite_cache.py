from __future__ import annotations

import abc
import annotated_types
import ast
import asyncio
import collections
import dataclasses
import pathlib
import textwrap
import threading
import typing

import sqlite3

from . import _base

type Key = str

type LoadsValue[Return] = typing.Callable[[bytes], Return]
type DumpsKey[** Params] = typing.Callable[Params, Key]
type DumpsValue[Return] = typing.Callable[[Return], bytes]


@dataclasses.dataclass(frozen=True, kw_only=True)
class EnterContext[** Params, Return](
    _base.EnterContext[Params, Return],
    abc.ABC,
):
    connection: sqlite3.Connection
    dumps_key: DumpsKey[Params]
    dumps_value: DumpsValue[Return]
    exit_context_by_key: collections.OrderedDict[Key, ExitContext[Params, Return]]
    loads_value: LoadsValue[Return]
    table_name: str

    def __post_init__(
        self: AsyncEnterContext[Params, Return] | MultiEnterContext[Params, Return],
    ) -> None:
        self.connection.execute(textwrap.dedent(f'''
            CREATE TABLE IF NOT EXISTS `{self.table_name}` (
                key STRING PRIMARY KEY NOT NULL UNIQUE,
                value STRING NOT NULL
            )
        ''').strip())

    def __call__(
        self: AsyncEnterContext[Params, Return] | MultiEnterContext[Params, Return],
        key: Key,
    ):
        match self.connection.execute(
            f'SELECT value FROM `{self.table_name}` WHERE key = ?', (key,)
        ).fetchall():
            case [[value]]:
                return ast.literal_eval(value)
        exit_context = self.exit_context_by_key[key] = self.exit_context_t(
            connection=self.connection,
            dumps_value=self.dumps_value,
            key=key,
            table_name=self.table_name,
        )

        return exit_context, self.next_enter_context

    def __get__(self, instance, owner):
        with self.instance_lock:
            if (enter_context := self.enter_context_by_instance.get(instance)) is None:
                enter_context = self.enter_context_by_instance[instance] = dataclasses.replace(
                    self,
                    connection=self.connection,
                    instance=instance,
                    next_enter_context=self.next_enter_context.__get__(instance, owner),
                    table_name=f'{self.table_name}__{instance}',
                )
            return enter_context


@dataclasses.dataclass(frozen=True, kw_only=True)
class ExitContext[** Params, Return](
    _base.ExitContext[Params, Return],
    abc.ABC,
):
    connection: sqlite3.Connection
    dumps_value: DumpsValue[Return]
    key: Key
    table_name: str

    @abc.abstractmethod
    def __call__(
        self: AsyncExitContext[Params, Return] | MultiExitContext[Params, Return],
        result: _base.Raise | Return,
    ) -> Return:

        try:
            if isinstance(result, _base.Raise):
                raise result.e
            else:
                self.connection.execute(
                    f'''INSERT INTO `{self.table_name}` (key, value) VALUES (?, ?)''',
                    (self.key, self.dumps_value(result))
                )
                return result
        finally:
            self.event.set()


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncEnterContext[** Params, Return](
    EnterContext[Params, Return],
    _base.AsyncEnterContext[Params, Return],
):
    exit_context_by_key: collections.OrderedDict[Key, AsyncExitContext[Params, Return]] = dataclasses.field(
        default_factory=collections.OrderedDict
    )
    lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)

    async def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> (AsyncExitContext[Params, Return], _base.AsyncEnterContext[Params, Return]) | Return:
        key = self.dumps_key(*args, **kwargs)
        async with self.lock:
            if (exit_context := self.exit_context_by_key.get(key)) is not None:
                self.lock.release()
                try:
                    await exit_context.event.wait()
                finally:
                    await self.lock.acquire()
                self.exit_context_by_key.pop(key, None)

            return super().__call__(key)


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiEnterContext[** Params, Return](
    EnterContext[Params, Return],
    _base.MultiEnterContext[Params, Return],
):
    exit_context_by_key: collections.OrderedDict[Key, MultiExitContext[Params, Return]] = dataclasses.field(
        default_factory=collections.OrderedDict
    )
    lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)

    @property
    def exit_context_t(self) -> type[MultiExitContext]:
        return MultiExitContext

    def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> (MultiExitContext[Params, Return], _base.MultiEnterContext[Params, Return]) | Return:
        key = self.dumps_key(*args, **kwargs)
        with self.lock:
            if (exit_context := self.exit_context_by_key.get(key)) is not None:
                self.lock.release()
                try:
                    exit_context.event.wait()
                finally:
                    self.lock.acquire()
                self.exit_context_by_key.pop(key, None)

            return super().__call__(key)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncExitContext[** Params, Return](
    ExitContext[Params, Return],
    _base.AsyncExitContext[Params, Return],
):
    event: asyncio.Event = dataclasses.field(default_factory=asyncio.Event)

    async def __call__(self, result: _base.Raise | Return) -> Return:
        return super().__call__(result)


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiExitContext[** Params, Return](
    ExitContext[Params, Return],
    _base.MultiExitContext[Params, Return],
):
    event: threading.Event = dataclasses.field(default_factory=threading.Event)

    def __call__(self, result: _base.Raise | Return) -> Return:
        return super().__call__(result)


@dataclasses.dataclass(frozen=True, kw_only=True)
class Decorator[** Params, Return](_base.Decorator[Params, Return]):
    db_path: pathlib.Path | str = 'file::memory:?cache=shared'
    dumps_key: DumpsKey = ...
    dumps_value: DumpsValue[Return] = repr
    duration: typing.Annotated[float, annotated_types.Ge(0.0)] | None = None
    loads_value: LoadsValue[Return] = ast.literal_eval

    def __call__(
        self,
        decoratee: _base.Decoratee[Params, Return] | _base.Decorated[Params, Return],
        /,
    ) -> _base.Decorated[Params, Return]:
        decoratee = super().__call__(decoratee)

        if (dumps_key := self.dumps_key) is ...:
            def dumps_key(*args, **kwargs) -> Key:
                bound = decoratee.signature.bind(*args, **kwargs)
                bound.apply_defaults()
                return repr((bound.args, tuple(sorted(bound.kwargs))))

        match decoratee:
            case _base.AsyncDecorated():
                enter_context_t = AsyncEnterContext
            case _base.MultiDecorated():
                enter_context_t = MultiEnterContext
            case _: assert False, 'Unreachable'  # pragma: no cover

        decorated = self.register.decorateds[decoratee.register_key] = dataclasses.replace(
            decoratee,
            enter_context=enter_context_t(
                connection=sqlite3.connect(self.db_path, isolation_level=None),
                dumps_key=dumps_key,
                dumps_value=self.dumps_value,
                loads_value=self.loads_value,
                next_enter_context=decoratee.enter_context,
                table_name='__'.join(decoratee.register_key),
            ),
        )

        return decorated
