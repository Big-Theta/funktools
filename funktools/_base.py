from __future__ import annotations

import abc
import builtins
import dataclasses
import inspect
import re
import sys
import threading
import traceback
import types
import typing
import weakref

type Instance = object
type Name = typing.Annotated[str, annotated_types.Predicate(str.isidentifier)]  # noqa


@dataclasses.dataclass(frozen=True)
class Raise:
    exc_type: type[BaseException]
    exc_val: BaseException
    exc_tb: types.TracebackType


@dataclasses.dataclass(frozen=True, kw_only=True)
class Register(abc.ABC):
    class Key(tuple[str, ...]):
        def __str__(self) -> str:
            return '.'.join(self)

    decorateds: dict[Key, Decorated] = dataclasses.field(default_factory=dict)
    links: dict[Key, set[Name]] = dataclasses.field(default_factory=dict)


@typing.runtime_checkable
class Decoratee[** Params, Return](typing.Protocol):
    def __call__(*args: Params.args, **kwargs: Params.kwargs) -> typing.Awaitable[Return] | Return: ...


@typing.runtime_checkable
class AsyncDecoratee[** Params, Return](typing.Protocol):
    async def __call__(*args: Params.args, **kwargs: Params.kwargs) -> Return: ...


@typing.runtime_checkable
class MultiDecoratee[** Params, Return](typing.Protocol):
    def __call__(*args: Params.args, **kwargs: Params.kwargs) -> Return: ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class ContextBase[** Params, Return](
    abc.ABC
):
    enter_context_by_instance: weakref.WeakKeyDictionary[
        Instance, EnterContextBase[Params, Return]
    ] = dataclasses.field(default_factory=weakref.WeakKeyDictionary)
    instance: Instance | None = None
    instance_lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)

    @property
    @abc.abstractmethod
    def async_context_t(self) -> type[AsyncContext[Params, Return]]: ...

    @property
    @abc.abstractmethod
    def multi_context_t(self) -> type[MultiContext[Params, Return]]: ...

    @property
    @abc.abstractmethod
    def enter_context_t(self) -> type[EnterContext[Params, Return]]: ...

    @property
    @abc.abstractmethod
    def exit_context_t(self) -> type[ExitContext[Params, Return]]: ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncContextBase[** Params, Return](
    ContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiContextBase[** Params, Return](
    ContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class EnterContextBase[** Params, Return](
    ContextBase[Params, Return],
    abc.ABC,
):
    next_enter_context: EnterContextBase[Params, Return] | Base[Params, Return]

    @typing.overload
    async def __call__(
        self: AsyncEnterContextBase[Params, Return],
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> AsyncExitContextBase[Params, Return]: ...

    @typing.overload
    def __call__(
        self: MultiEnterContextBase[Params, Return],
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> MultiExitContextBase[Params, Return]: ...

    @abc.abstractmethod
    def __call__(self, *args, **kwargs): ...

    def __get__(self, instance: Instance, owner) -> EnterContextBase[Params, Return]:
        with self.instance_lock:
            if (enter_context := self.enter_context_by_instance.get(instance)) is None:
                enter_context = self.enter_context_by_instance[instance] = dataclasses.replace(self, instance=instance)
            return enter_context


@dataclasses.dataclass(frozen=True, kw_only=True)
class ExitContextBase[** Params, Return](
    ContextBase[Params, Return],
    abc.ABC,
):
    @typing.overload
    async def __call__(self: AsyncExitContextBase[Params, Return], return_: Raise | Return) -> None:
        ...

    @typing.overload
    def __call__(self: MultiExitContextBase[Params, Return], return_: Raise | Return) -> None:
        ...

    @abc.abstractmethod
    def __call__(self, return_): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncEnterContextBase[** Params, Return](
    AsyncContextBase[Params, Return],
    EnterContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiEnterContextBase[** Params, Return](
    MultiContextBase[Params, Return],
    EnterContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncExitContextBase[** Params, Return](
    AsyncContextBase[Params, Return],
    ExitContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiExitContextBase[** Params, Return](
    MultiContextBase[Params, Return],
    ExitContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class ContextMixin[** Params, Return](
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncContextMixin[** Params, Return](
    abc.ABC,
):

    @property
    def enter_context_t(self) -> type[AsyncEnterContext[Params, Return]]:
        return inspect.getmodule(self).AsyncEnterContext

    @property
    def exit_context_t(self) -> type[AsyncExitContext[Params, Return]]:
        return inspect.getmodule(self).AsyncExitContext


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiContextMixin[** Params, Return](
    abc.ABC,
):

    @property
    def enter_context_t(self) -> type[MultiEnterContext[Params, Return]]:
        return inspect.getmodule(self).MultiEnterContext

    @property
    def exit_context_t(self) -> type[MultiExitContext[Params, Return]]:
        return inspect.getmodule(self).MultiExitContext


@dataclasses.dataclass(frozen=True, kw_only=True)
class EnterContextMixin[** Params, Return](
    abc.ABC,
):

    @property
    def async_context_t(self) -> type[AsyncEnterContext[Params, Return]]:
        return inspect.getmodule(self).AsyncEnterContext

    @property
    def multi_context_t(self) -> type[MultiEnterContext[Params, Return]]:
        return inspect.getmodule(self).MultiEnterContext


@dataclasses.dataclass(frozen=True, kw_only=True)
class ExitContextMixin[** Params, Return](
    abc.ABC,
):
    @property
    def async_context_t(self) -> type[AsyncExitContext[Params, Return]]:
        return inspect.getmodule(self).AsyncExitContext

    @property
    def multi_context_t(self) -> type[MultiExitContext[Params, Return]]:
        return inspect.getmodule(self).MultiExitContext


@dataclasses.dataclass(frozen=True, kw_only=True)
class Context[** Params, Return](
    ContextMixin[Params, Return],
    ContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncContext[** Params, Return](
    AsyncContextMixin[Params, Return],
    AsyncContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiContext[** Params, Return](
    MultiContextMixin[Params, Return],
    MultiContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class EnterContext[** Params, Return](
    EnterContextMixin[Params, Return],
    EnterContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class ExitContext[** Params, Return](
    ExitContextMixin[Params, Return],
    ExitContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncEnterContextMixin[** Params, Return](
    AsyncContextMixin[Params, Return],
    EnterContextMixin[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiEnterContextMixin[** Params, Return](
    MultiContextMixin[Params, Return],
    EnterContextMixin[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncExitContextMixin[** Params, Return](
    AsyncContextMixin[Params, Return],
    ExitContextMixin[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiExitContextMixin[** Params, Return](
    MultiContextMixin[Params, Return],
    ExitContextMixin[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncEnterContext[** Params, Return](
    AsyncEnterContextMixin[Params, Return],
    AsyncContext[Params, Return],
    EnterContext[Params, Return],
    AsyncEnterContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiEnterContext[** Params, Return](
    MultiEnterContextMixin[Params, Return],
    MultiContext[Params, Return],
    EnterContext[Params, Return],
    MultiEnterContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncExitContext[** Params, Return](
    AsyncExitContextMixin[Params, Return],
    AsyncContext[Params, Return],
    ExitContext[Params, Return],
    AsyncExitContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiExitContext[** Params, Return](
    MultiExitContextMixin[Params, Return],
    MultiContext[Params, Return],
    ExitContext[Params, Return],
    MultiExitContextBase[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class Base[** Params, Return]:
    decoratee: Decoratee[Params, Return]

    def __get__(self, instance, owner) -> typing.Self:
        return self


@dataclasses.dataclass(frozen=True, kw_only=True)
class Decorated[** Params, Return](abc.ABC):
    enter_context: EnterContext[Params, Return] | Base[Params, Return]
    decorated_by_instance: weakref.WeakKeyDictionary[Instance, Decorated] = dataclasses.field(
        default_factory=weakref.WeakKeyDictionary
    )
    instance: Instance = ...
    instance_lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)
    register_key: Register.Key
    signature: inspect.Signature
    __doc__: str
    __module__: str
    __name__: str
    __qualname__: str

    @typing.overload
    async def __call__(self: AsyncDecorated[Params, Return], *args: Params.args, **kwargs: Params.kwargs) -> Return: ...

    @typing.overload
    def __call__(self: MultiDecorated[Params, Return], *args: Params.args, **kwargs: Params.kwargs) -> Return: ...

    @abc.abstractmethod
    def __call__(self): ...

    def __get__(self, instance: Instance, owner) -> Decorated[Params, Return]:
        with self.instance_lock:
            if (decorated := self.decorated_by_instance.get(instance)) is None:
                decorated = self.decorated_by_instance[instance] = dataclasses.replace(
                    self,
                    enter_context=self.enter_context.__get__(instance, owner),
                    instance=instance,
                )
            return decorated

    @staticmethod
    def norm_kwargs(kwargs: Params.kwargs) -> Params.kwargs:
        return dict(sorted(kwargs.items()))

    def norm_args(self, args: Params.args) -> Params.args:
        return args if self.instance is ... else [self.instance, *args]


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncDecorated[** Params, Return](Decorated[Params, Return]):
    enter_context: AsyncEnterContext[Params, Return] | Base[Params, Return]

    async def __call__(self, *args: Params.args, **kwargs: Params.kwargs) -> Return:
        args, kwargs = self.norm_args(args), self.norm_kwargs(kwargs)
        stack = [self.enter_context]
        result: Raise | Return = ...

        while stack:
            try:
                match item := stack.pop():
                    case Base():
                        stack.append(await item.decoratee(*args, **kwargs))
                    case EnterContextBase():
                        stack.append(await item(*args, **kwargs))
                    case ContextBase(), (Base() | ContextBase()):
                        stack += [*item]
                    case ExitContextBase():
                        stack.append(await item(result))
                    case result: ...
            except Exception:  # noqa
                stack.append(Raise(*sys.exc_info()))

        if isinstance(result, Raise):
            # TODO: there's more to be done with setting exception context
            raise result.exc_val

        return result


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiDecorated[** Params, Return](Decorated[Params, Return]):
    enter_context: MultiEnterContextBase[Params, Return] | Base[Params, Return]

    def __call__(self, *args: Params.args, **kwargs: Params.kwargs) -> Return:
        args, kwargs = self.norm_args(args), self.norm_kwargs(kwargs)
        stack = [self.enter_context]
        result: Raise | Return = ...

        while stack:
            try:
                match item := stack.pop():
                    case Base():
                        stack.append(item.decoratee(*args, **kwargs))
                    case EnterContextBase():
                        stack.append(item(*args, **kwargs))
                    case ContextBase(), (Base() | ContextBase()):
                        stack += [*item]
                    case ExitContextBase():
                        stack.append(item(result))
                    case result: ...
            except Exception:  # noqa
                stack.append(Raise(*sys.exc_info()))

        if isinstance(result, Raise):
            # TODO: there's more to be done with setting exception context
            raise result.exc_val

        return result


@dataclasses.dataclass(frozen=True, kw_only=True)
class Decorator[** Params, Return]:
    register: typing.ClassVar[Register] = Register()

    def __call__(
        self,
        decoratee: Decoratee[Params, Return] | Decorated[Params, Return],
        /,
    ) -> Decorated[Params, Return]:
        if isinstance(decoratee, Decorated):
            return decoratee

        register_key = Register.Key([
            *re.sub(r'.<.*>', '', '.'.join([decoratee.__module__, decoratee.__qualname__])).split('.')
        ])

        for i in range(len(register_key)):
            self.register.links.setdefault(Register.Key(register_key[:i]), set()).add(register_key[i])
        self.register.links.setdefault(register_key, set())

        if inspect.iscoroutinefunction(decoratee):
            decorated_t = AsyncDecorated
        else:
            decorated_t = MultiDecorated

        decorated = self.register.decorateds[register_key] = decorated_t(
                enter_context=Base(decoratee=decoratee),
                register_key=register_key,
                signature=inspect.signature(decoratee),
                __doc__=str(decoratee.__doc__),
                __module__=str(decoratee.__module__),
                __name__=str(decoratee.__name__),
                __qualname__=str(decoratee.__qualname__),
        )

        return decorated
