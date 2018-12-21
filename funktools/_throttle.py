from __future__ import annotations

import abc
import annotated_types
import asyncio
import dataclasses
import heapq
import sys
import threading
import time
import typing

from . import _base


type Condition = asyncio.Condition | threading.Condition
type Lock = asyncio.Lock | threading.Lock
type Penalty = typing.Annotated[float, annotated_types.Gt(0.0)]
type Time = typing.Annotated[float, annotated_types.Gt(0.0)]


class Pane:
    cooldown: typing.Annotated[float, annotated_types.Ge(0.0)] = 0.0
    size: typing.Annotated[int, annotated_types.Gt(0)] = sys.maxsize


# TODO: All of AIMDSemaphore belongs inside appropriate Async/Multi/Enter/Exit Contexts.
@dataclasses.dataclass(kw_only=True)
class AIMDSemaphore(abc.ABC):
    """Semaphore with AIMD behavior.

    Definitions:
        - hold - Callers that have acquired a semaphore value but have not released.
        - unit - Callers that `hold` and are allowed to begin execution within the current temporal `slice`.
        - wait - Callers that are waiting because the `max_herd` or `max_hold` limit would be exceeded.

        - slice - Discreet temporal checkpoint after which another `max_units` units are allowed through.
        - window - The amount of time that must pass after an individual slice expires before it is replenished.

    'value' behavior:
        - No more than the current `value` callers are approved to `hold`.
        - Value increases by 1 if a holder releases without raising an exception and the number of holders is greater
          than half of value.

    'checkpoint' behavior:
        -

    Value
    """
    additive_increase: typing.Annotated[int, annotated_types.Ge(0)]
    multiplicative_decrease: typing.Annotated[float, annotated_types.Interval[float](ge=0.0, le=1.0)]

    max_holders: int
    max_waiters: int

    value: int

    per_pane: int
    per_window: int
    window: typing.Annotated[float, annotated_types.Ge(0.0)]

    holders: int = 0
    holders_this_pane: int = 0
    panes: list[float] = dataclasses.field(default_factory=list)
    waiters: int = 0

    pane_pending: bool = False

    holders_condition_t: typing.ClassVar[type[asyncio.Condition] | type[threading.Condition]]
    holders_condition: holders_condition_t = ...

    panes_condition_t: typing.ClassVar[type[asyncio.Condition] | type[threading.Condition]]
    panes_condition: panes_condition_t = ...

    exception_t: typing.ClassVar[type[Exception]] = type('Exception', (Exception,), {})
    sleep_t: typing.ClassVar[type[asyncio.sleep] | type[time.sleep]]

    def __post_init__(self) -> None:
        self.holders_this_pane = self.per_pane

    def _release(self, ok: bool) -> None:
        match ok:
            case True if self.value <= 0:
                self.value = 1
            case True if self.additive_increase and (
                self.holders > self.value - int(self.value * self.multiplicative_decrease)
            ):
                self.value += self.additive_increase
                self.holders_condition.notify(self.additive_increase)
            case False if self.value > 0:
                self.value //= 2
            case False:
                self.value -= 1

        self.holders -= 1
        self.holders_condition.notify(1)


@dataclasses.dataclass(kw_only=True)
class AsyncAIMDSemaphore(AIMDSemaphore):
    holders_condition_t: typing.ClassVar[type[asyncio.Condition]] = asyncio.Condition
    panes_condition_t: typing.ClassVar[type[asyncio.Condition]] = asyncio.Condition

    holders_condition: asyncio.Condition = dataclasses.field(default_factory=holders_condition_t)
    panes_condition: asyncio.Condition = dataclasses.field(default_factory=panes_condition_t)

    @staticmethod
    async def _sleep(condition: asyncio.Condition, delay: float) -> None:
        condition.release()
        try:
            await asyncio.sleep(delay)
        finally:
            await condition.acquire()

    async def _wait(self, condition: asyncio.Condition) -> None:
        if self.waiters >= self.max_waiters:
            raise self.exception_t(f'{self.max_waiters=} exceeded.')

        self.waiters += 1
        try:
            await condition.wait()
        finally:
            self.waiters -= 1

    async def acquire(self) -> None:
        async with self.holders_condition:
            while self.holders >= max(1, min(self.value, self.max_holders)):
                await self._wait(self.holders_condition)
            self.holders += 1

            if self.value <= 0 and self.multiplicative_decrease:
                await self._sleep(self.holders_condition, (1 / self.multiplicative_decrease) ** -self.value)

        async with self.panes_condition:
            while self.holders_this_pane >= self.per_pane:
                if self.pane_pending:
                    await self._wait(self.panes_condition)
                elif not self.panes:
                    self.holders_this_pane = 0
                    heapq.heappush(self.panes, time.time() + self.window)
                elif self.panes[0] < (now := time.time()):
                    self.holders_this_pane = 0
                    heapq.heappushpop(self.panes, now + self.window)
                elif (len(self.panes) * self.per_pane) + self.holders_this_pane < self.per_window:
                    self.holders_this_pane = 0
                    heapq.heappush(self.panes, now + self.window)
                else:
                    self.pane_pending = True
                    await self._sleep(self.panes_condition, self.panes[0] - now)
                    self.pane_pending = False
                    self.holders_this_pane = 0
                    heapq.heappushpop(self.panes, self.panes[0] + self.window)
                    self.panes_condition.notify(self.per_pane + 1)
            self.holders_this_pane += 1

    async def release(self, ok: bool) -> None:
        async with self.holders_condition:
            self._release(ok)


@dataclasses.dataclass(kw_only=True)
class MultiAIMDSemaphore(AIMDSemaphore):
    holders_condition_t: typing.ClassVar[type[threading.Condition]] = threading.Condition
    panes_condition_t: typing.ClassVar[type[threading.Condition]] = threading.Condition

    holders_condition: threading.Condition = dataclasses.field(default_factory=holders_condition_t)
    panes_condition: threading.Condition = dataclasses.field(default_factory=panes_condition_t)

    @staticmethod
    def _sleep(condition: threading.Condition, delay: float) -> None:
        condition.release()
        try:
            time.sleep(delay)
        finally:
            condition.acquire()

    def _wait(self, condition: threading.Condition) -> None:
        if self.waiters >= self.max_waiters:
            raise self.exception_t(f'{self.max_waiters=} exceeded.')

        self.waiters += 1
        try:
            condition.wait()
        finally:
            self.waiters -= 1

    def acquire(self) -> None:
        with self.holders_condition:
            while self.holders >= max(1, min(self.value, self.max_holders)):
                self._wait(self.holders_condition)
            self.holders += 1

            if self.value <= 0 and self.multiplicative_decrease:
                self._sleep(self.holders_condition, (1 / self.multiplicative_decrease) ** -self.value)

        with self.panes_condition:
            while self.holders_this_pane >= self.per_pane:
                if self.pane_pending:
                    self._wait(self.panes_condition)
                elif not self.panes:
                    self.holders_this_pane = 0
                    heapq.heappush(self.panes, time.time() + self.window)
                elif self.panes[0] < (now := time.time()):
                    self.holders_this_pane = 0
                    heapq.heappushpop(self.panes, now + self.window)
                elif (len(self.panes) * self.per_pane) + self.holders_this_pane < self.per_window:
                    self.holders_this_pane = 0
                    heapq.heappush(self.panes, now + self.window)
                else:
                    self.pane_pending = True
                    self._sleep(self.panes_condition, self.panes[0] - now)
                    self.pane_pending = False
                    self.holders_this_pane = 0
                    heapq.heappushpop(self.panes, self.panes[0] + self.window)
                    self.panes_condition.notify(self.per_pane + 1)
            self.holders_this_pane += 1

    def release(self, ok: bool) -> None:
        with self.holders_condition:
            self._release(ok)


@dataclasses.dataclass(frozen=True, kw_only=True)
class Context[** Params, Return](_base.ContextBase, abc.ABC):
    semaphore: AIMDSemaphore

    semaphore_t = AIMDSemaphore


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncContext[** Params, Return](
    Context[Params, Return],
    _base.AsyncContext[Params, Return],
    abc.ABC,
):
    semaphore: AsyncAIMDSemaphore

    semaphore_t: typing.ClassVar = AsyncAIMDSemaphore


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiContext[** Params, Return](
    Context[Params, Return],
    _base.MultiContext[Params, Return],
    abc.ABC,
):
    semaphore: MultiAIMDSemaphore

    semaphore_t: typing.ClassVar = MultiAIMDSemaphore


@dataclasses.dataclass(frozen=True, kw_only=True)
class EnterContext[** Params, Return](
    Context[Params, Return],
    _base.EnterContext[Params, Return],
    abc.ABC,
):
    start: int

    @abc.abstractmethod
    def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> (ExitContext[Params, Return], _base.EnterContext[Params, Return]):
        return self.exit_context_t(semaphore=self.semaphore), self.next_enter_context

    def __get__(self, instance: _base.Instance, owner) -> typing.Self:
        with self.instance_lock:
            if (enter_context := self.enter_context_by_instance.get(instance)) is None:
                enter_context = self.enter_context_by_instance[instance] = dataclasses.replace(
                    self,
                    semaphore=self.semaphore_t(
                        additive_increase=self.semaphore.additive_increase,
                        multiplicative_decrease=self.semaphore.multiplicative_decrease,
                        max_holders=self.semaphore.max_holders,
                        max_waiters=self.semaphore.max_waiters,
                        per_pane=self.semaphore.per_pane,
                        per_window=self.semaphore.per_window,
                        value=self.start,
                        window=self.semaphore.window,
                    ),
                    start=self.start,
                )
            return enter_context


@dataclasses.dataclass(frozen=True, kw_only=True)
class ExitContext[** Params, Return](
    Context[Params, Return],
    _base.ExitContext[Params, Return],
    abc.ABC,
): ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncEnterContext[** Params, Return](
    EnterContext[Params, Return],
    AsyncContext[Params, Return],
    _base.AsyncEnterContext[Params, Return],
):
    async def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> (AsyncExitContext[Params, Return], _base.AsyncEnterContext[Params, Return]):
        await self.semaphore.acquire()
        return super().__call__(*args, **kwargs)


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiEnterContext[** Params, Return](
    EnterContext[Params, Return],
    MultiContext[Params, Return],
    _base.MultiEnterContext[Params, Return],
):
    def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> (MultiExitContext[Params, Return], _base.MultiEnterContext[Params, Return]):
        self.semaphore.acquire()
        return super().__call__(*args, **kwargs)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AsyncExitContext[** Params, Return](
    ExitContext[Params, Return],
    AsyncContext[Params, Return],
    _base.AsyncExitContext[Params, Return],
):

    semaphore: AsyncAIMDSemaphore
    semaphore_t: typing.ClassVar = AsyncAIMDSemaphore

    async def __call__(self, result: _base.Raise | Return) -> _base.Raise | Return:
        if isinstance(result, _base.Raise):
            await self.semaphore.release(ok=False)
        else:
            await self.semaphore.release(ok=True)
        return result


@dataclasses.dataclass(frozen=True, kw_only=True)
class MultiExitContext[** Params, Return](
    ExitContext[Params, Return],
    MultiContext[Params, Return],
    _base.MultiExitContext[Params, Return],
):
    semaphore: MultiAIMDSemaphore
    semaphore_t: typing.ClassVar = MultiAIMDSemaphore

    def __call__(self, result: _base.Raise | Return) -> _base.Raise | Return:
        if isinstance(result, _base.Raise):
            self.semaphore.release(ok=False)
        else:
            self.semaphore.release(ok=True)
        return result


@dataclasses.dataclass(frozen=True, kw_only=True)
class Decorator[** Params, Return](_base.Decorator[Params, Return]):
    additive_increase: typing.Annotated[int, annotated_types.Ge(0)] = 1
    multiplicative_decrease: typing.Annotated[float, annotated_types.Interval[float](ge=0.0, le=1.0)] = .5

    # How many callees are allowed through concurrently before additional callees become waiters.
    max_holders: typing.Annotated[int, annotated_types.Gt(0)] = sys.maxsize

    # How many callees are allowed through or to wait concurrently before additional callees are rejected.
    max_waiters: typing.Annotated[int, annotated_types.Gt(0)] = sys.maxsize

    # How many concurrent tokens to initialize with. This will never exceed given `soft` or `hard` values. Scaling
    #  follows AIMD control-flow rules. if this value is 1 and calls continue to fail, acquiring a token will incur an
    #  exponentially-increasing wait starting at 1 second before allowing the context to move forward.
    start: typing.Annotated[int, annotated_types.Gt(0)] = 1
    window: typing.Annotated[float, annotated_types.Ge(0.0)] = 0.0

    per_pane: int = sys.maxsize
    per_window: int = sys.maxsize

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

        decoratee = self.register.decorateds[decoratee.register_key] = dataclasses.replace(
            decoratee,
            enter_context=enter_context_t(
                semaphore=enter_context_t.semaphore_t(
                    additive_increase=self.additive_increase if self.multiplicative_decrease else 0,
                    multiplicative_decrease=self.multiplicative_decrease if self.additive_increase else 0.0,
                    max_holders=self.max_holders,
                    max_waiters=self.max_waiters,
                    per_pane=min(self.per_pane, self.per_window),
                    per_window=self.per_window,
                    value=self.start,
                    window=self.window,
                ),
                next_enter_context=decoratee.enter_context,
                start=self.start,
            ),
        )

        return decoratee
