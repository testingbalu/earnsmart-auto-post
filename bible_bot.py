import os
import json
import random
import textwrap
import hashlib
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont


# ============================================================
# CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
BIBLE_CHANNEL_ID = os.environ.get("BIBLE_CHANNEL_ID")
POST_TYPE = os.environ.get("POST_TYPE", "verse")

# You can change this later if required.
GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.5-flash"
)

TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
)

GEMINI_API = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

DATA_DIR = Path("data")
HISTORY_FILE = DATA_DIR / "bible_history.json"

DATA_DIR.mkdir(exist_ok=True)


# ============================================================
# BASIC VALIDATION
# ============================================================

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY secret is missing.")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN secret is missing.")

if not BIBLE_CHANNEL_ID:
    raise RuntimeError(
        "BIBLE_CHANNEL_ID secret is missing."
    )


# ============================================================
# TELEGRAM
# ============================================================

def telegram_request(method, payload=None, files=None):
    url = f"{TELEGRAM_API}/{method}"

    response = requests.post(
        url,
        data=payload,
        files=files,
        timeout=60
    )

    try:
        result = response.json()
    except Exception:
        raise RuntimeError(
            f"Telegram returned invalid response: "
            f"{response.text[:500]}"
        )

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result}"
        )

    return result


def send_message(text):
    return telegram_request(
        "sendMessage",
        {
            "chat_id": BIBLE_CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
    )


def send_photo(image_path, caption):
    with open(image_path, "rb") as photo:
        return telegram_request(
            "sendPhoto",
            payload={
                "chat_id": BIBLE_CHANNEL_ID,
                "caption": caption,
                "parse_mode": "HTML"
            },
            files={
                "photo": photo
            }
        )


def send_quiz(question, options, correct_index, explanation):
    return telegram_request(
        "sendPoll",
        {
            "chat_id": BIBLE_CHANNEL_ID,
            "question": question,
            "options": json.dumps(
                options,
                ensure_ascii=False
            ),
            "type": "quiz",
            "correct_option_id": str(correct_index),
            "is_anonymous": "true",
            "explanation": explanation,
            "explanation_parse_mode": "HTML"
        }
    )


# ============================================================
# GEMINI
# ============================================================

def gemini(prompt):
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json"
        }
    }

    response = requests.post(
        GEMINI_API,
        params={
            "key": GEMINI_API_KEY
        },
        json=payload,
        timeout=90
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Gemini API error {response.status_code}: "
            f"{response.text[:1000]}"
        )

    data = response.json()

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError(
            f"Unexpected Gemini response: {data}"
        )

    # Remove accidental markdown fences.
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "", 1)
        text = text.replace("```", "")
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"Gemini did not return valid JSON:\n{text}"
        )


# ============================================================
# HISTORY
# ============================================================

def load_history():
    if not HISTORY_FILE.exists():
        return {
            "verses": [],
            "quizzes": [],
            "knowledge": []
        }

    try:
        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)
    except Exception:
        return {
            "verses": [],
            "quizzes": [],
            "knowledge": []
        }


def save_history(history):
    with open(
        HISTORY_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            history,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# TELUGU BIBLE CONTENT
# ============================================================

def generate_verse(history):

    previous = history.get("verses", [])[-50:]

    prompt = f"""
You are creating content for a Telugu Christian Telegram channel.

Create ONE Bible verse post.

Requirements:

1. Telugu language.
2. Use a genuine Bible verse.
3. Do NOT invent or paraphrase the Bible verse.
4. Give the exact Telugu verse text as commonly used in Telugu Bibles.
5. Give the Bible reference.
6. Select an encouraging verse suitable for a daily Bible post.
7. Avoid verses already used recently.

Recently used references:
{json.dumps(previous, ensure_ascii=False)}

Return ONLY valid JSON:

{{
  "reference": "బైబిల్ గ్రంథం అధ్యాయం:వచనం",
  "verse": "తెలుగు బైబిల్ వచనం",
  "short_message": "ఒక చిన్న ప్రోత్సాహక సందేశం"
}}
"""

    return gemini(prompt)


def generate_quiz(history):

    previous = history.get("quizzes", [])[-100:]

    prompt = f"""
You are a Telugu Christian Bible quiz creator.

Create ONE high-quality Bible quiz question.

Requirements:

1. Telugu only.
2. The answer must be clearly supported by the Bible.
3. Four options.
4. Only ONE option is correct.
5. Questions should be suitable for normal Telugu Christian readers.
6. Do not create ambiguous questions.
7. Do not repeat recently used questions.
8. Include a Bible reference supporting the answer.
9. Return the index of the correct answer from 0 to 3.

Previously used questions:
{json.dumps(previous, ensure_ascii=False)}

Return ONLY JSON:

{{
  "question": "ప్రశ్న?",
  "options": [
    "ఎంపిక 1",
    "ఎంపిక 2",
    "ఎంపిక 3",
    "ఎంపిక 4"
  ],
  "correct_index": 0,
  "reference": "బైబిల్ సూచన",
  "explanation": "సరైన సమాధానం ఎందుకు సరైనదో చిన్న వివరణ"
}}
"""

    return gemini(prompt)


def generate_knowledge(history):

    previous = history.get("knowledge", [])[-100:]

    prompt = f"""
Create ONE interesting Telugu Bible knowledge quiz.

This is for a Telegram Christian channel.

Requirements:

- Telugu language.
- Four answer choices.
- Exactly one correct answer.
- Bible-based.
- Factually accurate.
- Interesting enough that people will want to vote.
- Include Bible reference.
- Avoid recently used questions.
- No trick questions.

Previously used:
{json.dumps(previous, ensure_ascii=False)}

Return ONLY JSON:

{{
  "question": "ప్రశ్న?",
  "options": [
    "ఎంపిక 1",
    "ఎంపిక 2",
    "ఎంపిక 3",
    "ఎంపిక 4"
  ],
  "correct_index": 0,
  "reference": "బైబిల్ సూచన",
  "explanation": "చిన్న వివరణ"
}}
"""

    return gemini(prompt)


# ============================================================
# IMAGE GENERATION
# ============================================================

def get_telugu_font(size):
    possible_fonts = [
        "/usr/share/fonts/truetype/noto/NotoSansTelugu-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansTelugu-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSerifTelugu-Regular.ttf"
    ]

    for font in possible_fonts:
        if os.path.exists(font):
            return ImageFont.truetype(font, size)

    raise RuntimeError(
        "Telugu font not found."
    )


def get_font(size, bold=False):

    if bold:
        possible = [
            "/usr/share/fonts/truetype/noto/NotoSansTelugu-Bold.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansTelugu-Bold.ttf"
        ]

        for path in possible:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)

    return get_telugu_font(size)


def create_bible_image(verse_data):

    width = 1080
    height = 1350

    image = Image.new(
        "RGB",
        (width, height),
        (18, 35, 45)
    )

    draw = ImageDraw.Draw(image)

    # Sky gradient
    for y in range(height):
        ratio = y / height

        r = int(20 + 80 * ratio)
        g = int(35 + 50 * ratio)
        b = int(55 + 15 * ratio)

        draw.line(
            [(0, y), (width, y)],
            fill=(r, g, b)
        )

    # Sun
    sun_x = 850
    sun_y = 220
    sun_r = 115

    draw.ellipse(
        [
            sun_x - sun_r,
            sun_y - sun_r,
            sun_x + sun_r,
            sun_y + sun_r
        ],
        fill=(245, 190, 90)
    )

    # Mountain silhouette
    mountain = [
        (0, 980),
        (180, 850),
        (330, 930),
        (520, 760),
        (690, 910),
        (830, 790),
        (1080, 950),
        (1080, 1350),
        (0, 1350)
    ]

    draw.polygon(
        mountain,
        fill=(15, 25, 28)
    )

    # Dark translucent-style panel
    draw.rounded_rectangle(
        [65, 180, 1015, 870],
        radius=40,
        fill=(10, 20, 25)
    )

    # Small heading
    heading_font = get_font(48, bold=True)

    draw.text(
        (540, 245),
        "నేటి బైబిల్ వాక్యం",
        font=heading_font,
        anchor="mm",
        fill=(240, 200, 100)
    )

    # Verse
    verse_font = get_font(54)

    verse = verse_data["verse"]

    lines = textwrap.wrap(
        verse,
        width=22
    )

    y = 390

    for line in lines:
        draw.text(
            (540, y),
            line,
            font=verse_font,
            anchor="mm",
            fill="white"
        )
        y += 82

    # Reference
    ref_font = get_font(43, bold=True)

    draw.text(
        (540, 790),
        verse_data["reference"],
        font=ref_font,
        anchor="mm",
        fill=(245, 190, 90)
    )

    # Bottom branding
    brand_font = get_font(36)

    draw.text(
        (540, 1240),
        "తెలుగు క్రైస్తవుల కోసం ❤️",
        font=brand_font,
        anchor="mm",
        fill="white"
    )

    output = DATA_DIR / "daily_bible_verse.jpg"

    image.save(
        output,
        quality=95
    )

    return output


# ============================================================
# POSTING
# ============================================================

def post_verse(history):

    data = generate_verse(history)

    image_path = create_bible_image(data)

    caption = (
        f"<b>📖 నేటి బైబిల్ వాక్యం</b>\n\n"
        f"📍 <b>{data['reference']}</b>\n\n"
        f"{data['short_message']}\n\n"
        f"🙏 దేవుని వాక్యాన్ని ధ్యానిద్దాం."
    )

    send_photo(
        image_path,
        caption
    )

    history["verses"].append(
        data["reference"]
    )

    history["verses"] = history["verses"][-200:]

    save_history(history)

    print("Bible verse posted successfully.")


def post_quiz(history):

    data = generate_quiz(history)

    validate_quiz(data)

    explanation = (
        f"📖 <b>{data['reference']}</b>\n\n"
        f"{data['explanation']}"
    )

    send_quiz(
        data["question"],
        data["options"],
        data["correct_index"],
        explanation
    )

    history["quizzes"].append(
        data["question"]
    )

    history["quizzes"] = history["quizzes"][-200:]

    save_history(history)

    print("Bible quiz posted successfully.")


def post_knowledge(history):

    data = generate_knowledge(history)

    validate_quiz(data)

    explanation = (
        f"📖 <b>{data['reference']}</b>\n\n"
        f"{data['explanation']}"
    )

    send_quiz(
        data["question"],
        data["options"],
        data["correct_index"],
        explanation
    )

    history["knowledge"].append(
        data["question"]
    )

    history["knowledge"] = history["knowledge"][-200:]

    save_history(history)

    print("Bible knowledge quiz posted successfully.")


# ============================================================
# VALIDATION
# ============================================================

def validate_quiz(data):

    if not isinstance(data, dict):
        raise RuntimeError(
            "Invalid quiz data."
        )

    required = [
        "question",
        "options",
        "correct_index",
        "reference",
        "explanation"
    ]

    for key in required:
        if key not in data:
            raise RuntimeError(
                f"Quiz missing field: {key}"
            )

    if len(data["options"]) != 4:
        raise RuntimeError(
            "Quiz must have exactly 4 options."
        )

    correct = data["correct_index"]

    if not isinstance(correct, int):
        raise RuntimeError(
            "correct_index must be an integer."
        )

    if correct < 0 or correct > 3:
        raise RuntimeError(
            "correct_index must be between 0 and 3."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("TELUGU BIBLE TELEGRAM BOT")
    print("=" * 60)
    print(f"Post type: {POST_TYPE}")
    print(
        "Time:",
        datetime.now().isoformat()
    )

    history = load_history()

    if POST_TYPE == "verse":
        post_verse(history)

    elif POST_TYPE == "quiz":
        post_quiz(history)

    elif POST_TYPE == "knowledge":
        post_knowledge(history)

    else:
        raise RuntimeError(
            f"Unknown POST_TYPE: {POST_TYPE}"
        )

    print("DONE.")


if __name__ == "__main__":
    main()
