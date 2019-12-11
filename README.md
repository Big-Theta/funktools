[![Build Status](https://travis-ci.org/cevans87/atools.svg?branch=master&kill_cache=1)](https://travis-ci.org/cevans87/atools)
[![Coverage Status](https://coveralls.io/repos/github/cevans87/atools/badge.svg?branch=master&kill_cache=1)](https://coveralls.io/github/cevans87/atools?branch=master)
# atools
Python 3.6+ decorators including

- __memoize__ - a function decorator for sync and async functions that memoizes results.
- __rate__ - a function decorator for sync and async functions that rate limits calls.

## memoize
    Decorates a function call and caches return value for given inputs.

    If 'db' is provided, memoized values will be saved to disk and reloaded during initialization.

    If 'duration' is provided, memoize will only retain return values for up to given 'duration'.

    If 'get_key' is provided, memoize will use the function to calculate the memoize hash key.

    If 'size' is provided, memoize will only retain up to 'size' return values.

    Examples:

        - Body will run once for unique input 'bar' and result is cached.
            @memoize
            def foo(bar) -> Any: ...

            foo(1)  # Function actually called. Result cached.
            foo(1)  # Function not called. Previously-cached result returned.
            foo(2)  # Function actually called. Result cached.

        - Same as above, but async.
            @memoize
            async def foo(bar) -> Any: ...

            # Concurrent calls from the same event loop are safe. Only one call is generated. The
            other nine calls in this example wait for the result.
            await asyncio.gather(*[foo(1) for _ in range(10)])

        - Classes may be memoized.
            @memoize
            Class Foo:
                def init(self, _): ...

            Foo(1)  # Instance is actually created.
            Foo(1)  # Instance not created. Previously-cached instance returned.
            Foo(2)  # Instance is actually created.

        - Calls to foo(1), foo(bar=1), and foo(1, baz='baz') are equivalent and only cached once
            @memoize
            def foo(bar, baz='baz'): ...

        - Only 2 items are cached. Acts as an LRU.
            @memoize(size=2)
            def foo(bar) -> Any: ...

            foo(1)  # LRU cache order [foo(1)]
            foo(2)  # LRU cache order [foo(1), foo(2)]
            foo(1)  # LRU cache order [foo(2), foo(1)]
            foo(3)  # LRU cache order [foo(1), foo(3)], foo(2) is evicted to keep cache size at 2

       - Items are evicted after 1 minute.
            @memoize(duration=datetime.timedelta(minutes=1))
            def foo(bar) -> Any: ...

            foo(1)  # Function actually called. Result cached.
            foo(1)  # Function not called. Previously-cached result returned.
            sleep(61)
            foo(1)  # Function actually called. Previously-cached result was too old.

        - Memoize can be explicitly reset through the function's 'memoize' attribute
            @memoize
            def foo(bar) -> Any: ...

            foo(1)  # Function actually called. Result cached.
            foo(1)  # Function not called. Previously-cached result returned.
            foo.memoize.reset()
            foo(1)  # Function actually called. Cache was emptied.

        - Current cache size can be accessed through the function's 'memoize' attribute
            @memoize
            def foo(bar) -> Any: ...

            foo(1)
            foo(2)
            len(foo.memoize)  # returns 2

        - Memoization hash keys can be generated from a non-default function:
            @memoize(get_key=lambda a, b, c: (a, b, c))
            def foo(a, b, c) -> Any: ...

        - If part of the returned key from get_key is awaitable, it will be awaited.
            async def await_something() -> Hashable: ...

            @memoize(get_key=lambda bar: (bar, await_something()))
            async def foo(bar) -> Any: ...

        - Properties can be memoized
            Class Foo:
                @property
                @memoize
                def bar(self): -> Any: ...

            a = Foo()
            a.bar  # Function actually called. Result cached.
            a.bar  # Function not called. Previously-cached result returned.

            b = Foo() # Memoize uses 'self' parameter in hash. 'b' does not share returns with 'a'
            b.bar  # Function actually called. Result cached.
            b.bar  # Function not called. Previously-cached result returned.

        - Be careful with eviction on methods.
            Class Foo:
                @memoize(size=1)
                def bar(self, baz): -> Any: ...

            a, b = Foo(), Foo()
            a.bar(1)  # LRU cache order [Foo.bar(a, 1)]
            b.bar(1)  # LRU cache order [Foo.bar(b, 1)], Foo.bar(a, 1) is evicted
            a.bar(1)  # Foo.bar(a, 1) is actually called and cached again.

        - The default memoize key generator can be overridden. The inputs must match the function's.
            Class Foo:
                @memoize(get_key=lambda self, a, b, c: (a, b, c))
                def bar(self, a, b, c) -> Any: ...

            a, b = Foo(), Foo()

            # Hash key will be (a, b, c)
            a.bar(1, 2, 3)  # LRU cache order [Foo.bar(a, 1, 2, 3)]

            # Hash key will again be (a, b, c)
            # Be aware, in this example the returned result comes from a.bar(...), not b.bar(...).
            b.bar(1, 2, 3)  # Function not called. Previously-cached result returned.

        - If the memoized function is async and any part of the key is awaitable, it is awaited.
            async def morph_a(a: int) -> int: ...

            @memoize(get_key=lambda a, b, c: (morph_a(a), b, c))
            def foo(a, b, c) -> Any: ...

        - Values can persist to disk and be reloaded when memoize is initialized again.

            @memoize(db=True)
            def foo(a) -> Any: ...

            foo(1)  # Function actually called. Result cached.

            # Process is restarted. Upon restart, the state of the memoize decorator is reloaded.

            foo(1)  # Function not called. Previously-cached result returned.

        - Be careful with 'db' and memoize values that don't hash consistently upon process restart.

            class Foo:
                @classmethod
                @memoize(db=True)
                def bar(cls, a) -> Any: ...

            Foo.bar(1)  # Function actually called. Result cached.
            Foo.bar(1)  # Function not called. Previously-cached result returned.

            # Process is restarted. Upon restart, the state of the memoize decorator is reloaded.

            # Hash value of 'cls', is now different.
            Foo.bar(1)  # Function actually called. Result cached.

            # You can create a consistent hash key to avoid this.
            class Foo:
                @classmethod
                @memoize(db=True, get_key=lambda cls: (f'{cls.__package__}:{cls.__name__}', a))
                def bar(cls, a) -> Any: ...

        - Alternative location of 'db' can also be given as pathlib.Path or str.
            @memoize(db=Path.home() / 'foo_memoize')
            def foo() -> Any: ...

            @memoize(db='~/bar_memoize')
            def bar() -> Any: ...

## rate
    Function decorator that rate limits the number of calls to function.

    'size' must be provided. It specifies the maximum number of calls that may be made concurrently
      and optionally within a given 'duration' time window.

    If 'duration' is provided, the maximum number of calls is limited to 'size' calls in any given
      'duration' time window.

    Examples:
        - Only 2 concurrent calls allowed.
            @rate(size=2)
            def foo(): ...

        - Only 2 calls allowed per minute.
            @rate(size=2, duration=60)
            def foo(): ...

        - Same as above, but duration specified with a timedelta.
            @rate_window(size=2, duration=datetime.timedelta(minutes=1))
            def foo(): ...

        - Same as above, but async.
            @rate_window(size=2, duration=datetime.timedelta(minutes=1))
            async def foo(): ...
