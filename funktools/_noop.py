from __future__ import annotations
import abc
import dataclasses
import typing

from . import _base


@dataclasses.dataclass(frozen=True, kw_only=True)
class ContextBase[** Params, Return](
    _base.ContextBase[Params, Return],
    abc.ABC,
):
    enter_context_t: typing.ClassVar[type[EnterContextBase]]
    exit_context_t: typing.ClassVar[type[ExitContextBase]]


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncContextBase[** Params, Return](
    ContextBase[Params, Return],
    _base.AsyncContextBase[Params, Return],
    abc.ABC,
):
    enter_context_t: typing.ClassVar[type[AsyncEnterContextBase]]
    exit_context_t: typing.ClassVar[type[AsyncExitContextBase]]


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiContextBase[** Params, Return](
    ContextBase[Params, Return],
    _base.MultiContextBase[Params, Return],
    abc.ABC,
):
    enter_context_t: typing.ClassVar[type[MultiEnterContextBase]]
    exit_context_t: typing.ClassVar[type[MultiExitContext]]


@dataclasses.dataclass(frozen=True, kw_only=True)
class EnterContextBase[** Params, Return](
    ContextBase[Params, Return],
    _base.EnterContextBase[Params, Return],
    abc.ABC,
):
    ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncEnterContextBase[** Params, Return](
    EnterContextBase[Params, Return],
    AsyncContextBase[Params, Return],
    _base.AsyncEnterContextBase[Params, Return],
    abc.ABC,
):
    ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiEnterContextBase[** Params, Return](
    EnterContextBase[Params, Return],
    MultiContextBase[Params, Return],
    _base.MultiEnterContextBase[Params, Return],
    abc.ABC,
):
    ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class ExitContextBase[** Params, Return](
    ContextBase[Params, Return],
    _base.ExitContextBase[Params, Return],
    abc.ABC,
):
    ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncExitContextBase[** Params, Return](
    ExitContextBase[Params, Return],
    AsyncContextBase[Params, Return],
    _base.AsyncExitContextBaseBase[Params, Return],
):
    ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiExitContext[** Params, Return](
    ExitContextBase[Params, Return],
    MultiContextBase[Params, Return],
    _base.MultiExitContextBase[Params, Return],
):
    ...


AsyncContextBase.enter_context_t = AsyncEnterContextBase
MultiContextBase.enter_context_t = MultiEnterContextBase
AsyncContextBase.exit_context_t = AsyncExitContextBase
MultiContextBase.exit_context_t = MultiExitContext


@dataclasses.dataclass(frozen=True, kw_only=True)
class Decorator[**Params, Return]:

    @typing.overload
    def __call__(
        self, decoratee: _base.AsyncDecoratee[Params, Return] | _base.AsyncDecorated[Params, Return], /
    ) -> _base.AsyncDecorated[Params, Return]: ...

    @typing.overload
    def __call__(
        self, decoratee: _base.MultiDecoratee[Params, Return] | _base.MultiDecorated[Params, Return], /
    ) -> _base.MultiDecorated[Params, Return]: ...

    def __call__(self, decoratee):
        if not isinstance(decoratee, _base.Decorated):
            decoratee = _base.Decorator[Params, Return]()(decoratee)

        match decoratee:
            case _base.AsyncDecorated():
                enter_context_t = AsyncEnterContextBase
            case _base.MultiDecorated():
                enter_context_t = MultiEnterContextBase
            case _: assert False, 'Unreachable'

        enter_context: EnterContextBase[Params, Return] = enter_context_t()

        decorated: _base.Decorated[Params, Return] = dataclasses.replace(
            decoratee, enter_contexts=tuple([enter_context, *decoratee.enter_contexts])
        )

        decorated.register.decorateds[decorated.register_key] = decorated

        return decorated
