from __future__ import annotations

import abc
import dataclasses
import inspect
import logging
import types
import typing

from . import _base


Level = typing.Literal['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET']


@dataclasses.dataclass(frozen=True, kw_only=True)
class EnterContext[** Params, Return](
    _base.EnterContext,
    abc.ABC,
):
    call_level: Level
    err_level: Level
    logger: logging.Logger
    ok_level: Level
    signature: inspect.Signature

    @abc.abstractmethod
    def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> (ExitContext[Params, Return], _base.EnterContext[Params, Return]):
        bound_arguments = self.signature.bind(*args, **kwargs)

        self.logger.log(
            logging.getLevelNamesMapping()[self.call_level],
            '%s',
            bound_arguments,
        )

        return self.exit_context_t(
            bound_arguments=bound_arguments,
            err_level=self.err_level,
            logger=self.logger,
            ok_level=self.ok_level,
        ), self.next_enter_context


@dataclasses.dataclass(frozen=True, kw_only=True)
class ExitContext[** Params, Return](
    _base.ExitContext,
    abc.ABC,
):
    bound_arguments: inspect.BoundArguments
    err_level: Level
    logger: logging.Logger
    ok_level: Level

    @abc.abstractmethod
    def __call__(
        self,
        result: _base.Raise | Return
    ) -> _base.Raise | Return:
        if isinstance(result, _base.Raise):
            self.logger.log(
                logging.getLevelNamesMapping()[self.err_level],
                '%s raised %s',
                self.bound_arguments, result.exc_val,
                #exc_info=(result.exc_type, result.exc_val, result.exc_tb),
            )
        else:
            self.logger.log(
                logging.getLevelNamesMapping()[self.ok_level],
                '%s -> %s',
                self.bound_arguments,
                result,
            )

        return result


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncEnterContext[** Params, Return](
    EnterContext[Params, Return],
    _base.AsyncEnterContext[Params, Return],
):
    async def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs
    ) -> tuple[AsyncExitContext[Params, Return], _base.AsyncEnterContext[Params, Return]] | Return:
        return super().__call__(*args, **kwargs)


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiEnterContext[** Params, Return](
    EnterContext[Params, Return],
    _base.MultiEnterContext[Params, Return],
):

    def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs
    ) -> tuple[MultiExitContext[Params, Return], _base.MultiEnterContext[Params, Return]] | Return:
        return super().__call__(*args, **kwargs)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncExitContext[** Params, Return](
    ExitContext[Params, Return],
    _base.AsyncExitContext[Params, Return],
):

    async def __call__(self, result: _base.Raise | Return) -> _base.Raise | Return:
        return super().__call__(result)


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiExitContext[** Params, Return](
    ExitContext[Params, Return],
    _base.MultiExitContext[Params, Return],
):

    def __call__(self, result: _base.Raise | Return) -> _base.Raise | Return:
        return super().__call__(result)


@dataclasses.dataclass(frozen=True, kw_only=True)
class Decorator[** Params, Return](_base.Decorator[Params, Return]):
    call_level: Level = 'DEBUG'
    err_level: Level = 'ERROR'
    logger: logging.Logger = ...
    ok_level: Level = 'INFO'

    def __call__(
        self,
        decoratee: _base.Decoratee[Params, Return] | _base.Decorated[Params, Return],
        /,
    ) -> _base.Decorated[Params, Return]:
        decoratee = super().__call__(decoratee)

        match decoratee:
            case _base.AsyncDecorated():
                enter_context_t = AsyncEnterContext[Params, Return]
            case _base.MultiDecorated():
                enter_context_t = MultiEnterContext[Params, Return]
            case _: assert False, 'Unreachable'  # pragma: no cover

        logger = logging.getLogger(str(decoratee.register_key)) if self.logger is ... else self.logger

        decorated = self.register.decorateds[decoratee.register_key] = dataclasses.replace(
            decoratee,
            enter_context=enter_context_t(
                call_level=self.call_level,
                err_level=self.err_level,
                logger=logger,
                next_enter_context=decoratee.enter_context,
                ok_level=self.ok_level,
                signature=decoratee.signature,
            ),
        )

        return decorated
