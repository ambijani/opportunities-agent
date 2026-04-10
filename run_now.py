"""Run the pipeline once immediately (for testing)."""
import asyncio
import config
from database.db import Database
from discord_bot.bot import OpportunitiesBot
from pipeline.runner import run_pipeline


async def main():
    db = Database(config.DB_PATH)
    bot = OpportunitiesBot()
    await bot.start()
    await run_pipeline(bot, db)
    await bot.close()


asyncio.run(main())
