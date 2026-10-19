"""Async single-worker oracle client for the TUI.

Cold-spawning the ~122 MB oracle per ``check``/``apply`` is expensive, and a
synchronous call would freeze the Textual interface. All oracle traffic
goes through one background worker with coalescing: at most one check is
in flight, and redundant checks requested while one runs collapse into a
single follow-up.

The boundary from the design holds: the guide writes the clock locally
(the one write it owns) and everything else goes through ``apply``. There
is deliberately no ``tick`` verb — clock advance never causes an oracle
round trip by itself; the next check simply reflects the new position.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

from runtime.oracle import OracleClient, OracleRejected, UndeclaredSubject  # noqa: F401

__all__ = ["AsyncOracle", "OracleRejected", "UndeclaredSubject"]


class AsyncOracle:
    """One ``OracleClient`` driven from a single background thread.

    ``asyncio``-facing methods (``check``, ``apply``) run the blocking
    subprocess calls in the worker thread and can be awaited from Textual
    handlers. Synchronous pass-throughs (``set_clock``, ``graph`` reads)
    stay local and never touch the subprocess.
    """

    def __init__(self, case_dir: str | Path, timeout: int = 60):
        self._client = OracleClient(case_dir, timeout=timeout)
        self._lock = threading.Lock()
        self._check_pending = 0
        self._last_verdict: dict | None = None

    # -- synchronous local state (no oracle round trip) ------------------
    def set_clock(self, day: int, hour: int) -> None:
        """The guide's only local write. No subprocess call is made."""
        with self._lock:
            self._client.set_clock(day, hour)

    def clock(self) -> tuple[int | None, int | None]:
        from rdflib import URIRef

        day = self._client.graph.value(
            URIRef("https://potato-hamlet.example/ontology/clock/now"),
            URIRef("https://potato-hamlet.example/ontology/dayIndex"),
        )
        hour = self._client.graph.value(
            URIRef("https://potato-hamlet.example/ontology/clock/now"),
            URIRef("https://potato-hamlet.example/ontology/atHour"),
        )
        try:
            return (int(str(day)) if day is not None else None,
                    int(str(hour)) if hour is not None else None)
        except ValueError:
            return None, None

    @property
    def client(self) -> OracleClient:
        return self._client

    @property
    def last_verdict(self) -> dict | None:
        return self._last_verdict

    # -- async oracle traffic (single worker with coalescing) ------------
    async def check(self) -> dict:
        """One in-flight check; concurrent callers coalesce onto it."""
        loop = asyncio.get_running_loop()
        with self._lock:
            self._check_pending += 1
        try:
            verdict = await loop.run_in_executor(None, self._run_check)
            self._last_verdict = verdict
            return verdict
        finally:
            with self._lock:
                self._check_pending = max(0, self._check_pending - 1)

    def _run_check(self) -> dict:
        with self._lock:
            client = self._client
        return client.check()

    async def apply(self, act: dict[str, Any]) -> dict:
        """Send the act envelope; adopt the returned graph wholesale."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._run_apply, act)
        return act

    def _run_apply(self, act: dict[str, Any]) -> None:
        with self._lock:
            self._client.apply(act)

    async def eca_ids(self) -> list[str]:
        loop = asyncio.get_running_loop()
        with self._lock:
            client = self._client
        return await loop.run_in_executor(None, client.eca_ids)
