from __future__ import annotations

import asyncio

from eixo import BytesSource, DocumentEngine, InspectionRequest, PDFProviderUnavailableError


async def main() -> None:
    source = BytesSource(
        content=b"%PDF-1.7\n",
        filename="example.pdf",
        declared_media_type="application/pdf",
        size=9,
    )
    async with DocumentEngine.local() as engine:
        try:
            await engine.inspect(InspectionRequest(source=source))
        except PDFProviderUnavailableError as error:
            print(error.code)


if __name__ == "__main__":
    asyncio.run(main())
