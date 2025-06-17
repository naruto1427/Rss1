import feedparser
import asyncio
import json
import logging
import os

from aiohttp import web
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === Config ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
owner = 123456789  # <-- Replace with your Telegram user ID
TARGET_CHAT_ID = owner
SOURCE_FILE = "sources.json"
CHECK_INTERVAL = 20  # 1 minute

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
last_seen_links = {}

# === Telegram Commands ===
def load_sources():
    try:
        with open(SOURCE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_sources(sources):
    with open(SOURCE_FILE, "w") as f:
        json.dump(sources, f, indent=4)

async def check_feeds(bot: Bot):
    while True:
        sources = load_sources()
        for name, url in sources.items():
            feed = feedparser.parse(url)
            if feed.entries:
                for entry in feed.entries[:5]:
                    if entry.link not in last_seen_links.get(name, []):
                        text = f"🔹 <b>{entry.title}</b>\n{entry.link}"
                        await bot.send_message(chat_id=TARGET_CHAT_ID, text=text, parse_mode="HTML")
                        last_seen_links.setdefault(name, []).append(entry.link)
                        last_seen_links[name] = last_seen_links[name][-20:]
        await asyncio.sleep(CHECK_INTERVAL)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != owner:
        return
    await update.message.reply_text("✅ Nyaa RSS Bot is running!")

async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != owner:
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /addsource <name> <rss_url>")
        return
    name, url = context.args
    sources = load_sources()
    sources[name] = url
    save_sources(sources)
    await update.message.reply_text(f"✅ Added source `{name}`.", parse_mode="Markdown")

async def remove_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != owner:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removesource <name>")
        return
    name = context.args[0]
    sources = load_sources()
    if name in sources:
        del sources[name]
        save_sources(sources)
        await update.message.reply_text(f"❌ Removed source `{name}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Source not found.")

async def list_sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != owner:
        return
    sources = load_sources()
    if not sources:
        await update.message.reply_text("No sources added.")
        return
    text = "\n".join([f"- `{name}`: {url}" for name, url in sources.items()])
    await update.message.reply_text(text, parse_mode="Markdown")

# === Web Server for Render ===
async def handle_health(request):
    return web.Response(text="Bot is alive!")

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addsource", add_source))
    app.add_handler(CommandHandler("removesource", remove_source))
    app.add_handler(CommandHandler("listsources", list_sources))

    # Start background task for feed checking
    asyncio.create_task(check_feeds(app.bot))

    # Start dummy web server
    runner = web.AppRunner(web.Application())
    runner.app.router.add_get("/", handle_health)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
