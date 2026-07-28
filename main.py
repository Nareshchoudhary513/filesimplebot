"""
main.py

FileStoreBot - a simple, professional Telegram file storage bot.

Flow overview
-------------
1. An admin sends a file (document/video/photo/audio) to the bot in a
   private chat. The bot saves its file_id in MongoDB and immediately
   replies with a permanent, shareable link (this is the "Gen Link"
   feature -- every upload is turned into a link on the spot).
2. Admins can also build a batch: /batch starts a collection session,
   every file sent afterwards is added to it in order, and /done
   finalizes it into a single batch link that delivers every file when
   opened.
3. Anyone opening a generated link (single or batch) is first checked
   against the configured force-subscribe channel; if they haven't
   joined, they're shown a "Join Channel" button and asked to try
   again.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Dict, List, Optional

from pyrogram import Client, filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
import database
from shortener import shorten_url

# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

app = Client(
    name=config.SESSION_NAME,
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)

# In-memory state for active /batch collection sessions.
# Maps admin user_id -> list of file_codes collected so far.
_active_batches: Dict[int, List[str]] = {}

SUPPORTED_MEDIA_FILTER = filters.document | filters.video | filters.photo | filters.audio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_media_info(message: Message) -> Optional[dict]:
    """Pull (file_id, file_unique_id, file_name, file_size, file_type)
    out of any supported media message."""
    if message.document:
        media, file_type = message.document, "document"
    elif message.video:
        media, file_type = message.video, "video"
    elif message.photo:
        media, file_type = message.photo, "photo"
    elif message.audio:
        media, file_type = message.audio, "audio"
    else:
        return None

    file_name = getattr(media, "file_name", None) or f"{file_type}_{media.file_unique_id}"
    return {
        "file_id": media.file_id,
        "file_unique_id": media.file_unique_id,
        "file_name": file_name,
        "file_size": getattr(media, "file_size", 0) or 0,
        "file_type": file_type,
    }


def build_share_link(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start={code}"


async def get_channel_invite_link(client: Client) -> Optional[str]:
    """Build a joinable link for the force-subscribe channel, whether it
    was configured as a @username or a numeric chat id."""
    channel = config.FORCE_SUB_CHANNEL
    if not channel:
        return None

    if channel.lstrip("-").isdigit():
        try:
            chat = await client.get_chat(int(channel))
            if chat.invite_link:
                return chat.invite_link
            return await client.export_chat_invite_link(int(channel))
        except Exception:
            return None

    return f"https://t.me/{channel.lstrip('@')}"


async def is_subscribed(client: Client, user_id: int) -> bool:
    """Check whether a user has joined the force-subscribe channel.
    Returns True (i.e. allow access) if force-subscribe is disabled."""
    channel = config.FORCE_SUB_CHANNEL
    if not channel:
        return True

    chat_id: int | str = int(channel) if channel.lstrip("-").isdigit() else channel

    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status not in ("left", "kicked", "banned")
    except UserNotParticipant:
        return False
    except Exception:
        # If the check itself fails (e.g. bot isn't admin there), fail
        # open so a misconfiguration doesn't lock everyone out.
        return True


def force_sub_markup(invite_link: Optional[str]) -> InlineKeyboardMarkup:
    rows = []
    if invite_link:
        rows.append([InlineKeyboardButton("📢 Join Channel", url=invite_link)])
    rows.append([InlineKeyboardButton("🔄 Try Again", callback_data="check_sub")])
    return InlineKeyboardMarkup(rows)


async def send_stored_file(client: Client, chat_id: int, file_doc: dict) -> None:
    """Deliver one stored file to a chat using its saved file_id."""
    caption = file_doc.get("caption") or file_doc.get("file_name")
    file_type = file_doc["file_type"]
    file_id = file_doc["file_id"]

    if file_type == "document":
        await client.send_document(chat_id, file_id, caption=caption)
    elif file_type == "video":
        await client.send_video(chat_id, file_id, caption=caption)
    elif file_type == "photo":
        await client.send_photo(chat_id, file_id, caption=caption)
    elif file_type == "audio":
        await client.send_audio(chat_id, file_id, caption=caption)


# ---------------------------------------------------------------------------
# /start (including deep-link file / batch delivery)
# ---------------------------------------------------------------------------


@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message) -> None:
    user_id = message.from_user.id

    if not await is_subscribed(client, user_id):
        invite_link = await get_channel_invite_link(client)
        await message.reply_text(
            "🔒 **You must join our channel before using this bot.**\n\n"
            "Tap the button below to join, then press *Try Again*.",
            reply_markup=force_sub_markup(invite_link),
        )
        return

    payload = message.command[1] if len(message.command) > 1 else None

    if not payload:
        await message.reply_text(
            f"👋 **Hello {message.from_user.first_name}!**\n\n"
            "I'm a File Store Bot. I can deliver files via permanent "
            "share links."
            + ("\n\nAdmins can send me a file directly to generate a link." if config.is_admin(user_id) else "")
        )
        return

    if payload.startswith("batch_"):
        await deliver_batch(client, message, payload)
    else:
        await deliver_single_file(client, message, payload)


async def deliver_single_file(client: Client, message: Message, file_code: str) -> None:
    file_doc = await database.get_file(file_code)
    if not file_doc:
        await message.reply_text("❌ This link is invalid or the file no longer exists.")
        return
    await send_stored_file(client, message.chat.id, file_doc)


async def deliver_batch(client: Client, message: Message, batch_code: str) -> None:
    batch_doc = await database.get_batch(batch_code)
    if not batch_doc:
        await message.reply_text("❌ This batch link is invalid or has expired.")
        return

    files = await database.get_files_by_codes(batch_doc["file_codes"])
    if not files:
        await message.reply_text("❌ This batch is empty.")
        return

    status = await message.reply_text(f"📦 Sending {len(files)} file(s), please wait...")
    sent = 0
    for file_doc in files:
        try:
            await send_stored_file(client, message.chat.id, file_doc)
            sent += 1
            await asyncio.sleep(0.5)  # gentle pacing to avoid flood limits
        except Exception:
            continue

    await status.edit_text(f"✅ Sent {sent}/{len(files)} file(s).")


# ---------------------------------------------------------------------------
# Force-subscribe "Try Again" callback
# ---------------------------------------------------------------------------


@app.on_callback_query(filters.regex("^check_sub$"))
async def check_sub_callback(client: Client, callback_query: CallbackQuery) -> None:
    user_id = callback_query.from_user.id

    if await is_subscribed(client, user_id):
        await callback_query.message.edit_text(
            "✅ **Thanks for joining!** Send /start again to continue."
        )
        await callback_query.answer("Access granted!")
    else:
        await callback_query.answer(
            "You haven't joined the channel yet. Please join and try again.",
            show_alert=True,
        )


# ---------------------------------------------------------------------------
# File storage + automatic Gen Link (admins only)
# ---------------------------------------------------------------------------


@app.on_message(SUPPORTED_MEDIA_FILTER & filters.private)
async def store_file_handler(client: Client, message: Message) -> None:
    user_id = message.from_user.id

    if not config.is_admin(user_id):
        await message.reply_text("🚫 Only admins are allowed to upload files.")
        return

    info = extract_media_info(message)
    if info is None:
        await message.reply_text("❌ Unsupported file type.")
        return

    caption = message.caption.html if message.caption else None
    file_code = await database.save_file(
        file_id=info["file_id"],
        file_unique_id=info["file_unique_id"],
        file_name=info["file_name"],
        file_size=info["file_size"],
        file_type=info["file_type"],
        uploaded_by=user_id,
        caption=caption,
    )

    # If the admin currently has an active /batch session, add this file
    # to it instead of (also) generating a standalone single-file link.
    if user_id in _active_batches:
        _active_batches[user_id].append(file_code)
        await message.reply_text(
            f"➕ Added to batch (**{len(_active_batches[user_id])}** file(s) so far). "
            "Send /done when finished, or /cancelbatch to discard."
        )
        return

    bot_username = client.me.username if client.me else (await client.get_me()).username
    share_link = build_share_link(bot_username, file_code)
    short_link = await shorten_url(share_link)

    await message.reply_text(
        "✅ **File stored and link generated!**\n\n"
        f"🔗 Share link:\n{short_link}",
        disable_web_page_preview=True,
    )


# ---------------------------------------------------------------------------
# Batch link commands (admins only)
# ---------------------------------------------------------------------------


@app.on_message(filters.command("batch") & filters.private)
async def batch_start_handler(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    if not config.is_admin(user_id):
        await message.reply_text("🚫 Only admins can create batch links.")
        return

    if user_id in _active_batches:
        await message.reply_text(
            "⚠️ You already have an active batch session.\n"
            "Send /done to finish it or /cancelbatch to discard it."
        )
        return

    _active_batches[user_id] = []
    await message.reply_text(
        "📦 **Batch session started.**\n\n"
        "Send me the files you want to include, one after another, in "
        "the order you want them delivered. When finished, send /done."
    )


@app.on_message(filters.command("cancelbatch") & filters.private)
async def batch_cancel_handler(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    if _active_batches.pop(user_id, None) is None:
        await message.reply_text("You don't have an active batch session.")
    else:
        await message.reply_text("🗑️ Batch session cancelled.")


@app.on_message(filters.command("done") & filters.private)
async def batch_done_handler(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    if not config.is_admin(user_id):
        return

    file_codes = _active_batches.pop(user_id, None)
    if file_codes is None:
        await message.reply_text("You don't have an active batch session. Start one with /batch.")
        return

    if not file_codes:
        await message.reply_text("⚠️ No files were added to this batch. Session discarded.")
        return

    batch_code = await database.create_batch(file_codes, created_by=user_id)
    bot_username = client.me.username if client.me else (await client.get_me()).username
    share_link = build_share_link(bot_username, batch_code)
    short_link = await shorten_url(share_link)

    await message.reply_text(
        f"✅ **Batch finalized with {len(file_codes)} file(s)!**\n\n"
        f"🔗 Share link:\n{short_link}",
        disable_web_page_preview=True,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _startup_checks() -> None:
    config.validate()
    try:
        await database.ping()
    except Exception as exc:
        print(f"[FATAL] Could not connect to MongoDB: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(_startup_checks())
    print("FileStoreBot is starting...")
    app.run()
