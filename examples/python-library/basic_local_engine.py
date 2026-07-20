from __future__ import annotations

import asyncio

from eixo import DocumentEngine, __version__


async def main() -> None:
    async with DocumentEngine.local() as engine:
        print(f"eixo {__version__}")
        print(engine.runtime.config.max_concurrent_tasks)


if __name__ == "__main__":
    asyncio.run(main())

