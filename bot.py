import os
import requests
import feedparser
import sqlite3
import hashlib
import time
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

# Config from GitHub Secrets
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL = os.getenv('CHANNEL')
DB_FILE = '/tmp/posted_deals.db'  # Temp for GitHub Actions

bot = Bot(token=BOT_TOKEN)

# Create DB
conn = sqlite3.connect(DB_FILE)
conn.execute('''CREATE TABLE IF NOT EXISTS posted 
                (id TEXT PRIMARY KEY, message_id INTEGER, expiry INTEGER)''')
conn.commit()

def hash_url(url):
    return hashlib.md5(url.encode()).hexdigest()

def post_deal(title, url, expiry_hours=24):
    deal_id = hash_url(url)
    if conn.execute("SELECT 1 FROM posted WHERE id=?", (deal_id,)).fetchone():
        return  # Skip duplicate
    
    text = f"🔥 *LOOT ALERT: {title}*\n\n🛒 Grab now: {url}\n\n⏰ Expires soon – Auto deletes when over!"
    if expiry_hours:
        expiry_ts = int(time.time()) + (expiry_hours * 3600)
        text += f"\n\n*Ends in ~{expiry_hours}h*"
    
    try:
        message = bot.send_message(chat_id=CHANNEL, text=text, parse_mode='Markdown', disable_web_page_preview=True)
        
        # Save for auto-delete
        conn.execute("INSERT INTO posted VALUES (?, ?, ?)", (deal_id, message.message_id, expiry_ts))
        conn.commit()
        print(f"Posted: {title}")
    except TelegramError as e:
        print(f"Error posting: {e}")

def delete_expired():
    now = int(time.time())
    expired = conn.execute("SELECT message_id FROM posted WHERE expiry > 0 AND expiry < ?", (now,)).fetchall()
    for (msg_id,) in expired:
        try:
            bot.delete_message(chat_id=CHANNEL, message_id=msg_id)
            conn.execute("DELETE FROM posted WHERE message_id=?", (msg_id,))
            print(f"Deleted expired message {msg_id}")
        except:
            pass
    conn.commit()

def check_rss_feeds():
    # DesiDime Hot Deals (free RSS, India-focused loots)
    feed_url = "https://www.desidime.com/rss/hot-deals"
    feed = feedparser.parse(feed_url)
    for entry in feed.entries[:5]:  # Top 5 latest
        title = entry.title
        url = entry.link
        # Simple expiry guess (most loots <24h)
        expiry = 12  # hours
        if "till" in entry.summary.lower() or "valid until" in entry.summary.lower():
            expiry = 6  # Shorter for time-sensitive
        post_deal(title, url, expiry)
    
    # Add more sources later (Amazon RSS via affiliate, etc.)

if __name__ == "__main__":
    delete_expired()  # Clean old posts first
    check_rss_feeds()  # Post new ones
    print("Loot bot run complete!")
