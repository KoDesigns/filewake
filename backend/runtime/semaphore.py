from __future__ import annotations

import asyncio

from backend.config import get_settings


conversion_semaphore = asyncio.Semaphore(get_settings().max_parallel_conversions)
