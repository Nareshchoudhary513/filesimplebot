"""
database.py

Async MongoDB access layer (via Motor) for FileStoreBot.

Two collections are used:

    files   -> one document per stored file, keyed by a unique `file_code`
    batches -> one document per batch link, holding an ordered list of
               the file_codes that belong to it
"""

from __future__ import annotations

import datetime as dt
import secrets
import string
from dataclasses import dataclass, field, asdict
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorClient

import config

# ---- Connection setup ----
_client: AsyncIOMotorClient = AsyncIOMotorClient(config.MONGO_URI)
_db = _client[config.DATABASE_NAME]

files_collection = _db["files"]
batches_collection = _db["batches"]

_CODE_ALPHABET = string.ascii_letters + string.digits


def _generate_code(length: int = 10) -> str:
    """Generate a short, URL-safe random code for use in deep links."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


@dataclass
class StoredFile:
    """Represents one file stored in MongoDB."""

    file_code: str
    file_id: str
    file_unique_id: str
    file_name: str
    file_size: int
    file_type: str  # document | video | photo | audio
    caption: Optional[str]
    uploaded_by: int
    created_at: dt.datetime = field(default_factory=dt.datetime.utcnow)


async def ping() -> None:
    """Raise if MongoDB is unreachable; used for a startup health check."""
    await _client.admin.command("ping")


async def save_file(
    file_id: str,
    file_unique_id: str,
    file_name: str,
    file_size: int,
    file_type: str,
    uploaded_by: int,
    caption: Optional[str] = None,
) -> str:
    """Store a new file document and return its generated file_code."""
    file_code = _generate_code()
    stored = StoredFile(
        file_code=file_code,
        file_id=file_id,
        file_unique_id=file_unique_id,
        file_name=file_name,
        file_size=file_size,
        file_type=file_type,
        caption=caption,
        uploaded_by=uploaded_by,
    )
    await files_collection.insert_one(asdict(stored))
    return file_code


async def get_file(file_code: str) -> Optional[dict]:
    """Fetch a single stored file document by its file_code."""
    return await files_collection.find_one({"file_code": file_code})


async def create_batch(file_codes: List[str], created_by: int) -> str:
    """Create a batch document referencing an ordered list of file_codes
    and return its generated batch_code."""
    batch_code = "batch_" + _generate_code(12)
    await batches_collection.insert_one(
        {
            "batch_code": batch_code,
            "file_codes": file_codes,
            "created_by": created_by,
            "created_at": dt.datetime.utcnow(),
        }
    )
    return batch_code


async def get_batch(batch_code: str) -> Optional[dict]:
    """Fetch a batch document by its batch_code."""
    return await batches_collection.find_one({"batch_code": batch_code})


async def get_files_by_codes(file_codes: List[str]) -> List[dict]:
    """Fetch multiple stored file documents, preserving the given order."""
    cursor = files_collection.find({"file_code": {"$in": file_codes}})
    documents = {doc["file_code"]: doc async for doc in cursor}
    return [documents[code] for code in file_codes if code in documents]
