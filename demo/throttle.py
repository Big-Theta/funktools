import asyncio
import logging

import funktools

logger = logging.getLogger(__name__)


@funktools.CLI()
async def aimd(
    log_level: funktools.CLI.Annotated.log_level(logger) = 'ERROR',
    /,
) -> None:
    """Demo for throttling with AIMD.

    Ex: python3 -m demo throttle aimd
    """

    progress_by_client: dict[int, int] = {}

    @funktools.Throttle(
        start=128,  # Number of clients that can be served simultaneously.
        additive_increase=0,  # Do not increase number of clients to serve.
        max_waiters=128,  # Number of requests that may be queued before additional requests are rejected.
        multiplicative_decrease=0.0,  # Do not decrease number of clients to serve.
        per_window=512,  # Number of requests that can be served in window.
        window=1.0,  # Time frame.
    )
    async def server() -> None:
        await asyncio.sleep(.01)

    async def client(i) -> None:

        @funktools.Retry()
        @funktools.Throttle()
        async def api_call():
            await server()

        progress_by_client[i] = 0

        for _ in range(1024):
            await api_call()
            progress_by_client[i] += 1
        del progress_by_client[i]

    async def printer():
        while True:
            print(f'{progress_by_client=}')
            await asyncio.sleep(1.0)

    client_i = 0
    print('Press `Enter` to add clients.')
    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(printer())
        while True:
            await asyncio.get_running_loop().run_in_executor(None, input)
            task_group.create_task(client(client_i := client_i + 1))


if __name__ == '__main__':
    funktools.CLI().run(__name__)
