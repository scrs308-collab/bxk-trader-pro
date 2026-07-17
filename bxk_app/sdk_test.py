from tastytrade import Session
from tastytrade.dxfeed import DXLinkStreamer
import asyncio

from bxk_app.config import (
    TASTYTRADE_USERNAME,
    TASTYTRADE_PASSWORD,
)


async def test_dxlink():

    session = Session(
        TASTYTRADE_USERNAME,
        TASTYTRADE_PASSWORD,
    )

    streamer = await DXLinkStreamer.create(session)

    quote = await streamer.get_event(
        ".SPXW260706P7475"
    )

    

    await streamer.close()


if __name__ == "__main__":
    asyncio.run(test_dxlink())