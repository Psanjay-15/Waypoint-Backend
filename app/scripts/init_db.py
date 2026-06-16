"""Create the database schema: python -m app.scripts.init_db"""

import asyncio

from app.core.database import create_all
from app.core.logging import configure_logging, get_logger

log = get_logger(__name__)


async def main() -> None:
    await create_all()
    log.info("schema created")


if __name__ == "__main__":
    configure_logging()
    asyncio.run(main())
