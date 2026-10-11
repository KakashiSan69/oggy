#!/usr/bin/env python3
"""Initialize database tables."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import init_db
from src.config import settings

async def main():
    print(f"Initializing database at {settings.db_host}:{settings.db_port}/{settings.db_name}")
    await init_db()
    print("Database initialized successfully!")

if __name__ == "__main__":
    asyncio.run(main())