name: EarnSmart India Daily Post

on:
  workflow_dispatch:
  schedule:
    - cron: "30 3 * * *"

jobs:
  post-to-telegram:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.x"

      - name: Generate and publish daily post
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        run: |
          python - <<'PY'
          import os, sys, json, urllib.request, urllib.parse
          from datetime import datetime

          BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
          CHAT_ID = "@LegitEarnIndia"
          API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

          if not BOT_TOKEN:
              print("ERROR: TELEGRAM_BOT_TOKEN secret is missing.")
              sys.exit(1)

          def telegram_request(method, params):
              data = urllib.parse.urlencode(params).encode()
              req = urllib.request.Request(API_URL + "/" + method, data=data)
              try:
                  with urllib.request.urlopen(req) as resp:
                      body = resp.read().decode()
                      result = json.loads(body)
                      if not result.get("ok"):
                          print(f"Telegram API error: {result}")
                          sys.exit(1)
                      print(f"Telegram API success: message_id={result['result']['message_id']}")
                      return result
              except Exception as e:
                  print(f"HTTP error: {e}")
                  sys.exit(1)

          topics = [
              {
                  "title": "Start Freelancing With One Skill",
                  "image": "https://images.unsplash.com/photo-1553877522-43269d4ea984?auto=format&fit=crop&w=1200&q=85",
                  "content": """🔥 <b>EarnSmart India — Daily Opportunity</b>

<b>Topic: Start Freelancing With One Skill</b>

💡 <b>What is it?</b>
Freelancing means offering one skill as a service.

👤 <b>Who can start?</b>
Beginners with one marketable skill.

🛠 <b>Skills required</b>
• Communication
• Time management
• Proposal writing

🚀 <b>How to start</b>
1. Pick one skill
2. Practise daily
3. Build 3 sample projects
4. Create a portfolio
5. Apply only for relevant jobs

💼 <b>Where to find legitimate work</b>
• <a href="https://www.upwork.com">Upwork</a>
• <a href="https://www.fiverr.com">Fiverr</a>
• <a href="https://www.freelancer.com">Freelancer</a>

💰 <b>Earning reality</b>
Income varies by skill, experience, and workload.

⚠️ <b>Scam warning</b>
Never pay deposits to unlock jobs.

📅 <b>7-day action plan</b>
Day 1: Practise
Day 2: Build sample
Day 3: Portfolio
Day 4: Apply
Day 5: Improve
Day 6: Network
Day 7: Review progress

━━━━━━━━━━━━━━
<b>EarnSmart India</b>
Learn • Work • Earn Safely
━━━━━━━━━━━━━━"""
              }
              # Add more topics here...
          ]

          index = datetime.now().timetuple().tm_yday % len(topics)
          topic = topics[index]

          telegram_request("sendPhoto", {
              "chat_id": CHAT_ID,
              "photo": topic["image"],
              "caption": f"📅 {datetime.now().strftime('%d %B %Y')}\n<b>{topic['title']}</b>",
              "parse_mode": "HTML"
          })

          telegram_request("sendMessage", {
              "chat_id": CHAT_ID,
              "text": topic["content"],
              "parse_mode": "HTML"
          })
          PY
