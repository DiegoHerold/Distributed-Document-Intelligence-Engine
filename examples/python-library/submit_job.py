from __future__ import annotations

import asyncio

from eixo import BytesSource, DocumentEngine, ProcessingRequest


async def main() -> None:
    source = BytesSource(
        content=b"%PDF-1.7\n",
        filename="example.pdf",
        declared_media_type="application/pdf",
        size=9,
    )
    async with DocumentEngine.local() as engine:
        job = await engine.submit(ProcessingRequest(source=source))
        print(job.status.value)


if __name__ == "__main__":
    asyncio.run(main())
