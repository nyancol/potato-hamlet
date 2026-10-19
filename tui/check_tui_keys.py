import asyncio
import sys

sys.path.insert(0, ".")

from textual.widgets import Input

from tui.app import HamletGuideApp


async def main():
    app = HamletGuideApp(case_dir="cases/mayor-quorum")
    async with app.run_test() as pilot:
        await pilot.pause(3.0)
        print("BOOT-OK", flush=True)
        cmd = app.query_one("#cmd", Input)
        E = lambda v: type("E", (), {"value": v, "input": cmd})()
        await app.on_input_submitted(E("duty 0"))
        print("PENDING after cmd:", app.pending_confirm, flush=True)
        await pilot.press("n")
        print("N-OK pending:", app.pending_confirm, "log:", app.log_entries, flush=True)
        await app.on_input_submitted(E("duty 0"))
        await pilot.press("y")
        await pilot.pause(4.0)
        print("Y-OK pending:", app.pending_confirm, "log:", app.log_entries, flush=True)
        await pilot.press("r")
        await pilot.pause(3.0)
        print("R-OK phase:", app.verdict.get("phase"), flush=True)
        await pilot.press("q")
        await pilot.pause(1.0)
        print("Q-OK running:", app.is_running, flush=True)


asyncio.run(main())
print("DONE", flush=True)
