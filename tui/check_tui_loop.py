import asyncio
import sys

sys.path.insert(0, ".")

from tui.app import HamletGuideApp


async def main():
    app = HamletGuideApp(case_dir="cases/mayor-quorum")
    async with app.run_test():
        await asyncio.sleep(6)
        print("renders:", getattr(app, "_render_count", 0),
              "select_changed:", getattr(app, "_select_changed_count", 0), flush=True)
        await asyncio.sleep(6)
        print("renders:", getattr(app, "_render_count", 0),
              "select_changed:", getattr(app, "_select_changed_count", 0), flush=True)


asyncio.run(main())
print("DONE", flush=True)
