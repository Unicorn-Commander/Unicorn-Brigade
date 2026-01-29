"""
Database initialization script.
Creates tables and seeds initial agent data from JSON.

Usage:
    python -m app.db.init_db
"""
import asyncio
import json
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from app.db.database import engine, Base, async_session
from app.db.models import Agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def create_tables():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All database tables created successfully")


async def seed_agents():
    """Seed agents from JSON file if table is empty."""
    seed_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "seed_agents.json"
    )

    if not os.path.exists(seed_path):
        logger.warning(f"Seed file not found: {seed_path}")
        return

    async with async_session() as session:
        from sqlalchemy import select, func
        result = await session.execute(select(func.count(Agent.id)))
        count = result.scalar() or 0

        if count > 0:
            logger.info(f"Agents table already has {count} records, skipping seed")
            return

        with open(seed_path, "r") as f:
            agents_data = json.load(f)

        for data in agents_data:
            agent = Agent(
                id=data["id"],
                name=data["name"],
                display_name=data.get("displayName"),
                title=data.get("title"),
                rank=data.get("rank"),
                avatar=data.get("avatar", "🦄"),
                bio=data.get("bio"),
                persona=data.get("persona"),
                system_prompt=data.get("systemPrompt"),
                domain=data.get("domain", "general"),
                subdomain=data.get("subdomain"),
                status=data.get("status", "active"),
                type=data.get("type", "individual"),
                agent_type=data.get("agentType", "analysis"),
                capabilities=data.get("capabilities", []),
                model=data.get("model", "openai/gpt-4o-mini"),
                temperature=data.get("temperature", 0.7),
                max_tokens=data.get("maxTokens", 2000),
                tools=data.get("tools", []),
            )
            session.add(agent)

        await session.commit()
        logger.info(f"Seeded {len(agents_data)} agents from {seed_path}")


async def main():
    """Initialize database: create tables and seed data."""
    logger.info("Initializing Unicorn Brigade database...")
    await create_tables()
    await seed_agents()
    await engine.dispose()
    logger.info("Database initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())
