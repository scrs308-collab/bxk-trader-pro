import asyncio

from tastytrade import Session, DXLinkStreamer
from tastytrade.dxfeed import Quote

from bxk_app.config import (
    TASTYTRADE_CLIENT_SECRET,
    TASTYTRADE_REFRESH_TOKEN,
)


async def main():
    session = Session(
        TASTYTRADE_CLIENT_SECRET,
        TASTYTRADE_REFRESH_TOKEN,
    )

    symbols = [
        ".SPXW260706P7475",
        ".SPXW260706P7450",
        ".SPXW260706C7600",
        ".SPXW260706C7625",
    ]

    async with DXLinkStreamer(session) as streamer:
        await streamer.subscribe(Quote, symbols)

        for _ in range(4):
            quote = await streamer.get_event(Quote)
            


if __name__ == "__main__":
    asyncio.run(main())