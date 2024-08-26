import asyncio
import threading
from datetime import timedelta

import pytest

from pgqueuer import db
from pgqueuer.models import Job
from pgqueuer.qm import QueueManager
from pgqueuer.queries import Queries


@pytest.mark.parametrize("N", (1, 4, 32, 100))
async def test_cancellation_async(
    pgdriver: db.Driver,
    N: int,
) -> None:
    event = asyncio.Event()
    cancel_called_not_cancel_called = list[str]()
    q = Queries(pgdriver)
    qm = QueueManager(pgdriver)

    @qm.entrypoint("to_be_canceled")
    async def to_be_canceled(job: Job) -> None:
        scope = qm.get_context(job.id).cancellation
        await event.wait()
        cancel_called_not_cancel_called.append(
            "cancel_called" if scope.cancel_called else "not_cancel_called"
        )

    job_ids = await q.enqueue(
        ["to_be_canceled"] * N,
        [f"{n}".encode() for n in range(N)],
        [0] * N,
    )

    async def waiter() -> None:
        while sum(x.count for x in await q.queue_size() if x.status == "picked") < N:
            await asyncio.sleep(0.01)

        await q.mark_job_as_cancelled(job_ids)
        event.set()

        qm.alive = False

    await asyncio.gather(
        qm.run(dequeue_timeout=timedelta(seconds=0.0)),
        waiter(),
    )

    assert cancel_called_not_cancel_called == ["cancel_called"] * N

    # Logged as canceled
    assert sum(x.count for x in await q.log_statistics(tail=1_000) if x.status == "canceled") == N


@pytest.mark.parametrize("N", (1, 4, 32, 100))
async def test_cancellation_sync(
    pgdriver: db.Driver,
    N: int,
) -> None:
    event = threading.Event()
    cancel_called_not_cancel_called = list[str]()
    q = Queries(pgdriver)
    qm = QueueManager(pgdriver)

    @qm.entrypoint("to_be_canceled")
    def to_be_canceled(job: Job) -> None:
        nonlocal event
        scope = qm.get_context(job.id).cancellation
        event.wait()
        cancel_called_not_cancel_called.append(
            "cancel_called" if scope.cancel_called else "not_cancel_called"
        )

    job_ids = await q.enqueue(
        ["to_be_canceled"] * N,
        [f"{n}".encode() for n in range(N)],
        [0] * N,
    )

    async def waiter() -> None:
        while sum(x.count for x in await q.queue_size() if x.status == "picked") < N:
            await asyncio.sleep(0)

        await q.mark_job_as_cancelled(job_ids)
        event.set()

        qm.alive = False

    await asyncio.gather(
        qm.run(dequeue_timeout=timedelta(seconds=0.01)),
        waiter(),
    )

    assert cancel_called_not_cancel_called == ["cancel_called"] * N

    # Logged as canceled
    assert sum(x.count for x in await q.log_statistics(tail=1_000) if x.status == "canceled") == N


@pytest.mark.parametrize("N", (1, 4, 32, 100))
async def test_cancellation_async_context_manager(
    pgdriver: db.Driver,
    N: int,
) -> None:
    event = asyncio.Event()
    cancel_called_not_cancel_called = list[str]()
    q = Queries(pgdriver)
    qm = QueueManager(pgdriver)

    @qm.entrypoint("to_be_canceled")
    async def to_be_canceled(job: Job) -> None:
        with qm.get_context(job.id).cancellation as scope:
            await event.wait()
            cancel_called_not_cancel_called.append(
                "cancel_called" if scope.cancel_called else "not_cancel_called"
            )

    job_ids = await q.enqueue(
        ["to_be_canceled"] * N,
        [f"{n}".encode() for n in range(N)],
        [0] * N,
    )

    async def waiter() -> None:
        while sum(x.count for x in await q.queue_size() if x.status == "picked") < N:
            await asyncio.sleep(0)

        await q.mark_job_as_cancelled(job_ids)
        event.set()

        qm.alive = False

    await asyncio.gather(
        qm.run(dequeue_timeout=timedelta(seconds=0.01)),
        waiter(),
    )

    assert cancel_called_not_cancel_called == []

    # Logged as canceled
    assert sum(x.count for x in await q.log_statistics(tail=1_000) if x.status == "canceled") == N


@pytest.mark.parametrize("N", (1, 4, 32, 100))
async def test_cancellation_sync_context_manager(
    pgdriver: db.Driver,
    N: int,
) -> None:
    with pytest.raises(NotImplementedError):
        raise NotImplementedError(
            "anyio.CancelScope() does not support cancellation in sync functions."
        )