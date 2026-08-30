#!/usr/bin/env python3
"""
scripts/telegram_post.py
Sends a daily post to a Telegram channel using BOT token and CHAT ID.
- Exits non-zero on API errors so the GitHub Action will fail and show the Telegram error.
- Uses only Python stdlib so no additional dependencies are required.
"""

import os
import sys
import json
import random
import urllib.request
import urllib.parse
from datetime import datetime, timezone

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "@LegitEarnIndia")

if not BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN is missing. Set the secret in the repository settings.")
    sys.exit(1)

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# A small curated set of topics. You can expand this list as needed.
topics = [
    {
        "title": "Start Freelancing With One Skill",
        "intro": "You do not need dozens of skills to start freelancing. Pick one useful service, practise it and build proof of your work.",
        "image": "https://images.unsplash.com/photo-1553877522-43269d4ea984?auto=format&fit=crop&w=1200&q=85",
        "details": [
            "📋 JOB DESCRIPTION: Freelancers provide services to clients on a project or contract basis.",
            "🛠️ SKILLS NEEDED: One marketable skill, good communication, time management.",
            "🚀 HOW TO START: 1) Choose ONE service. 2) Practise. 3) Create sample projects.",
            "💡 TIP: Do not pay someone to 'unlock' guaranteed jobs."
        ]
    },
    {
        "title": "Learn WordPress Website Development",
        "intro": "WordPress skills can lead to website-building, maintenance and freelance opportunities.",
        "image": "https://images.unsplash.com/photo-1547658719-da2b51169166?auto=format&fit=crop&w=1200&q=85",
        "details": [
            "📋 JOB DESCRIPTION: Customize and maintain WordPress websites.",
            "🛠️ SKILLS NEEDED: WordPress admin, HTML/CSS, basic PHP.",
            "🚀 HOW TO START: Build 2-3 practice websites and create a portfolio.",
            "💡 TIP: Start with small fixes before complex sites."
        ]
    },
    {
        "title": "Learn Video Editing",
        "intro": "Video editing is useful for YouTube, Reels, Shorts and business content.",
        "image": "https://images.unsplash.com/photo-1574717024653-61fd2cf4d44d?auto=format&fit=crop&w=1200&q=85",
        "details": [
            "📋 JOB DESCRIPTION: Turn raw footage into finished videos.",
            "🛠️ SKILLS NEEDED: Editing software, storytelling, audio editing.",
            "🚀 HOW TO START: Learn an editor, make sample videos and build a showreel.",
            "💡 TIP: Short-form editing is a practical starting point."
        ]
    }
]


def api_call(method, params=None):
    """Call Telegram Bot API method with form-encoded POST and return parsed JSON."""
    url = f"{API_BASE}/{method}"
    data = None
    if params is None:
        params = {}
    try:
        data = urllib.parse.urlencode(params or {}).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            print("Telegram response:", body)
            result = json.loads(body)
            return result
    except Exception as e:
        print(f"ERROR: request to Telegram failed: {e}")
        raise


def choose_topic():
    return random.choice(topics)


def build_caption(topic):
    parts = [f"<b>{topic['title']}</b>", topic.get("intro", "")]
    parts += topic.get("details", [])
    caption = "\n\n".join([p for p in parts if p])
    # Telegram caption max length for photos is 1024 characters; truncate gracefully
    if len(caption) > 1000:
        caption = caption[:997] + "..."
    return caption


def main():
    topic = choose_topic()
    caption = build_caption(topic)

    # Try to send photo with caption. If that fails, fallback to sendMessage.
    try:
        params = {
            "chat_id": CHAT_ID,
            "photo": topic.get("image"),
            "caption": caption,
            "parse_mode": "HTML",
        }
        print("Sending sendPhoto with params chat_id=", CHAT_ID)
        res = api_call("sendPhoto", params)
        if not res.get("ok"):
            print("sendPhoto returned error:", res)
            # If photo posting fails with a known error, try text fallback
            raise RuntimeError("sendPhoto failed")
        print("Posted to Telegram successfully. Message id:", res.get("result", {}).get("message_id"))
        return
    except Exception:
        print("Falling back to sendMessage (text only)")
        try:
            text = f"{topic['title']}\n\n{topic.get('intro','')}\n\n" + "\n".join(topic.get('details', []))
            params = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
            res = api_call("sendMessage", params)
            if not res.get("ok"):
                print("sendMessage returned error:", res)
                print("Exiting with failure to surface the Telegram error in Action logs.")
                sys.exit(1)
            print("Posted text to Telegram successfully. Message id:", res.get("result", {}).get("message_id"))
            return
        except Exception as e:
            print("Final error while posting to Telegram:", e)
            sys.exit(1)


if __name__ == "__main__":
    main()
