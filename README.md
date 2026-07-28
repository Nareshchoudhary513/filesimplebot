# 📁 FileStoreBot

A simple, professional Telegram file storage bot built with **Pyrogram 2.x**
and **MongoDB** (via Motor). Admins upload files and instantly get a
permanent, shareable link back; anyone opening that link receives the file,
after (optionally) joining a required channel.

---

## ✨ Features

- `/start` command, including deep-link file & batch delivery
- Stores documents, videos, photos, and audio
- Saves Telegram file IDs in MongoDB for permanent, reusable links
- **Gen Link** — admins get a shareable link the moment they upload a file
- **Batch Links** — collect several files and share them all behind one link, delivered in order
- **Force Subscribe** — users must join a channel before the bot will serve files
- **URL Shortener** — pluggable, works with any generic shortener API, configured entirely via `.env`
- Simple admin system — admin ids come straight from `.env`

---

## 📂 Project Structure

```
FileStoreBot/
├── main.py            # Bot entrypoint and all handlers
├── config.py           # Environment-variable driven configuration
├── database.py          # MongoDB (Motor) access layer
├── shortener.py           # Pluggable URL shortener integration
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Installation

### 1. Clone and install dependencies

```bash
git clone https://github.com/yourusername/FileStoreBot.git
cd FileStoreBot

python3 -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Get your Telegram API credentials

1. Go to <https://my.telegram.org>, log in, and open **API Development Tools**.
2. Create an app and note your **API_ID** and **API_HASH**.

### 3. Create your bot with BotFather

1. Open [@BotFather](https://t.me/BotFather) on Telegram.
2. Send `/newbot` and follow the prompts.
3. Copy the **BOT_TOKEN** it gives you.

### 4. Set up MongoDB

- **Local:** install MongoDB Community Edition, use `mongodb://localhost:27017`.
- **Cloud (recommended):** create a free cluster at
  [MongoDB Atlas](https://www.mongodb.com/cloud/atlas), whitelist your IP,
  and copy the connection string into `MONGO_URI`.

### 5. Set up the force-subscribe channel (optional)

1. Create a Telegram channel and add the bot as an **admin**.
2. Set `FORCE_SUB_CHANNEL` to the channel's `@username` (without the `@`),
   or its numeric id if it's a private channel.
3. Leave `FORCE_SUB_CHANNEL` empty in `.env` to disable this feature.

### 6. Set up a URL shortener (optional)

Any shortener exposing `GET https://<base_url>/api?api=<key>&url=<link>`
works out of the box — just set `SHORTENER_API_KEY` and
`SHORTENER_BASE_URL`. Leave both empty to share full, unshortened links.
Switching providers never needs a code change, only new `.env` values.

### 7. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in every value — see the table below.

### 8. Run the bot

```bash
python main.py
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `API_ID` | ✅ | Telegram API ID from my.telegram.org |
| `API_HASH` | ✅ | Telegram API hash |
| `BOT_TOKEN` | ✅ | Bot token from BotFather |
| `MONGO_URI` | ✅ | MongoDB connection string |
| `DATABASE_NAME` | | Database name (default `filestorebot`) |
| `FORCE_SUB_CHANNEL` | | Channel username or id users must join before using the bot |
| `ADMINS` | ✅ | Comma-separated Telegram user ids allowed to generate links |
| `SHORTENER_API_KEY` | | API key for your chosen link shortener |
| `SHORTENER_BASE_URL` | | Base domain of your chosen link shortener |

---

## 🤖 Usage

**For admins:**

1. Send any document, video, photo, or audio file directly to the bot in
   a private chat. The bot stores it and immediately replies with a
   permanent share link.
2. To create a batch link:
   - Send `/batch` to start a session.
   - Send every file you want included, one by one, in order.
   - Send `/done` to finalize and receive one link for the whole batch.
   - Send `/cancelbatch` at any point to discard the session instead.

**For everyone:**

- Open a share link (`https://t.me/YourBot?start=<code>`) to receive the
  file (or every file in a batch).
- If force-subscribe is enabled, you'll be asked to join the required
  channel first, then press **Try Again**.

---

## 📜 License

Provided as-is for personal and commercial use. Please avoid re-uploading
this code verbatim as a "new" open-source project without modification.
