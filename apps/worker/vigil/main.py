"""
Vigil Worker — Entry point.

Starts the APScheduler and runs the polling engine.
"""

import asyncio
import logging

from vigil.polling import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vigil")


async def run() -> None:
    logger.info("Vigil worker starting...")
    scheduler = setup_scheduler()
    scheduler.start()
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Vigil worker received shutdown signal.")
    except Exception:
        logger.critical("Vigil worker crashed with unexpected error", exc_info=True)
    finally:
        # Close HTTP clients to release connection pools and SSL contexts.
        from vigil.polling import _ik_client, _sc_client

        if _ik_client is not None:
            try:
                await _ik_client.close()
            except Exception:
                logger.warning("Failed to close IK client", exc_info=True)
        if _sc_client is not None:
            try:
                await _sc_client.close()
            except Exception:
                logger.warning("Failed to close SC client", exc_info=True)

        scheduler.shutdown()
        logger.info("Vigil worker stopped.")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
