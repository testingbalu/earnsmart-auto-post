import os
import json
import random
import textwrap
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

# Keep the model that is currently working in your repository.
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


def send_quiz(
    question,
    options,
    correct_index,
    explanation
):

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
            "temperature": 0.65,
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

        text = (
            data["candidates"][0]
            ["content"]["parts"][0]["text"]
        )

    except Exception:

        raise RuntimeError(
            f"Unexpected Gemini response: {data}"
        )

    text = text.strip()

    # Remove accidental markdown fences.

    if text.startswith("```"):

        text = text.replace(
            "```json",
            "",
            1
        )

        text = text.replace(
            "```",
            ""
        )

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

            history = json.load(f)

            # Make sure old history files still work.

            history.setdefault(
                "verses",
                []
            )

            history.setdefault(
                "quizzes",
                []
            )

            history.setdefault(
                "knowledge",
                []
            )

            return history

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
# BIBLE VERSE GENERATION
# ============================================================

def generate_verse(history):

    previous = history.get(
        "verses",
        []
    )[-50:]

    prompt = f"""
You are creating content for the Telugu Christian Telegram
channel "TeluguChristiansWorld".

Create ONE daily Bible verse post.

IMPORTANT RULES:

1. Write in natural Telugu.
2. Use a genuine Bible verse.
3. Never invent a Bible verse.
4. Never create a fake Bible reference.
5. Do not paraphrase the actual verse.
6. Use commonly recognized Telugu Bible wording.
7. Select an encouraging, meaningful verse.
8. Avoid recently used references.
9. The short message should be useful and spiritually encouraging.
10. Do not include political, unrelated, promotional or job content.

Recently used Bible references:

{json.dumps(previous, ensure_ascii=False)}

Return ONLY valid JSON:

{{
  "reference": "బైబిల్ గ్రంథం అధ్యాయం:వచనం",
  "verse": "తెలుగు బైబిల్ వచనం",
  "short_message": "ఈ వాక్యం మనకు ఇచ్చే చిన్న ప్రోత్సాహక సందేశం"
}}
"""

    return gemini(prompt)


# ============================================================
# HIGH QUALITY BIBLE QUIZ
# ============================================================

def generate_quiz(history):

    previous = history.get(
        "quizzes",
        []
    )[-100:]

    prompt = f"""
You are an expert Telugu Bible teacher and Bible quiz creator.

Create ONE high-quality Bible quiz for the Telegram channel:

TeluguChristiansWorld

The purpose is:
- Bible learning
- Reader engagement
- Accurate Scripture knowledge
- Easy-to-understand Telugu

STRICT RULES:

1. The question MUST be based directly on the Bible.
2. Use natural Telugu.
3. Do not use awkward machine-translated Telugu.
4. Exactly FOUR answer options.
5. Exactly ONE option is correct.
6. The correct answer must be clearly supported by Scripture.
7. Give the exact Bible reference supporting the answer.
8. Do NOT create opinion questions.
9. Do NOT create trick questions.
10. Do NOT create ambiguous questions.
11. Do NOT invent Bible facts.
12. Do NOT invent people, places or events.
13. Do NOT mix two unrelated Bible facts.
14. Do NOT repeat a recently used question.
15. Wrong options should be believable but incorrect.
16. The question should teach something useful.
17. Vary topics between:
    - Bible people
    - prophets
    - apostles
    - kings
    - women in the Bible
    - miracles
    - places
    - numbers
    - books
    - teachings
    - important events
    - Old Testament
    - New Testament
18. Mix easy, medium and difficult questions.
19. Avoid making every question extremely easy.
20. Keep the question short enough for a Telegram quiz.
21. The explanation must clearly say why the correct answer is correct.
22. The explanation must be consistent with the Bible reference.
23. Do not include URLs.
24. Do not include advertisements.
25. Do not include job links.
26. Do not include unrelated content.

Recently used questions:

{json.dumps(previous, ensure_ascii=False)}

Return ONLY valid JSON.

Use exactly this structure:

{{
  "question": "బైబిల్ ఆధారంగా ప్రశ్న?",
  "options": [
    "ఎంపిక 1",
    "ఎంపిక 2",
    "ఎంపిక 3",
    "ఎంపిక 4"
  ],
  "correct_index": 0,
  "reference": "బైబిల్ గ్రంథం అధ్యాయం:వచనం",
  "explanation": "సరైన సమాధానం ఎందుకు సరైనదో స్పష్టంగా వివరించే చిన్న వివరణ."
}}

IMPORTANT:

correct_index must be:
0 for option 1
1 for option 2
2 for option 3
3 for option 4
"""

    return gemini(prompt)


# ============================================================
# BIBLE KNOWLEDGE QUIZ
# ============================================================

def generate_knowledge(history):

    previous = history.get(
        "knowledge",
        []
    )[-100:]

    prompt = f"""
You are an expert Telugu Bible teacher.

Create ONE interesting Bible knowledge quiz for:

TeluguChristiansWorld

This should make Telugu Christians want to learn more
about the Bible.

STRICT RULES:

1. Telugu language.
2. Natural Telugu.
3. Bible-based.
4. Factually accurate.
5. Exactly four options.
6. Exactly one correct answer.
7. The answer must be supported by Scripture.
8. Include the Bible reference.
9. No trick questions.
10. No opinion questions.
11. No ambiguous questions.
12. No invented facts.
13. No fake Bible references.
14. Do not repeat recently used questions.
15. Wrong options must be plausible.
16. Make the question educational.
17. Vary the topic.
18. Mix Old Testament and New Testament.
19. Mix easy, medium and difficult questions.
20. Keep the question concise.
21. Give a useful explanation.
22. No advertisements.
23. No job links.
24. No unrelated content.
25. No URLs.

Previously used questions:

{json.dumps(previous, ensure_ascii=False)}

Return ONLY valid JSON:

{{
  "question": "బైబిల్ జ్ఞాన ప్రశ్న?",
  "options": [
    "ఎంపిక 1",
    "ఎంపిక 2",
    "ఎంపిక 3",
    "ఎంపిక 4"
  ],
  "correct_index": 0,
  "reference": "బైబిల్ గ్రంథం అధ్యాయం:వచనం",
  "explanation": "సరైన సమాధానం మరియు బైబిల్ ఆధారాన్ని వివరించే చిన్న వివరణ."
}}

correct_index:
0 = option 1
1 = option 2
2 = option 3
3 = option 4
"""

    return gemini(prompt)


# ============================================================
# IMAGE / TELUGU FONT
# ============================================================

def get_telugu_font(size):

    possible_fonts = [

        "/usr/share/fonts/truetype/noto/"
        "NotoSansTelugu-Regular.ttf",

        "/usr/share/fonts/opentype/noto/"
        "NotoSansTelugu-Regular.ttf",

        "/usr/share/fonts/truetype/noto/"
        "NotoSerifTelugu-Regular.ttf"
    ]

    for font in possible_fonts:

        if os.path.exists(font):

            return ImageFont.truetype(
                font,
                size
            )

    raise RuntimeError(
        "Telugu font not found."
    )


def get_font(
    size,
    bold=False
):

    if bold:

        possible = [

            "/usr/share/fonts/truetype/noto/"
            "NotoSansTelugu-Bold.ttf",

            "/usr/share/fonts/opentype/noto/"
            "NotoSansTelugu-Bold.ttf"
        ]

        for path in possible:

            if os.path.exists(path):

                return ImageFont.truetype(
                    path,
                    size
                )

    return get_telugu_font(size)


# ============================================================
# BIBLE VERSE IMAGE
# ============================================================

def create_bible_image(verse_data):

    width = 1080
    height = 1350

    image = Image.new(
        "RGB",
        (width, height),
        (18, 35, 45)
    )

    draw = ImageDraw.Draw(image)

    # --------------------------------------------------------
    # SKY GRADIENT
    # --------------------------------------------------------

    for y in range(height):

        ratio = y / height

        r = int(
            20 + 80 * ratio
        )

        g = int(
            35 + 50 * ratio
        )

        b = int(
            55 + 15 * ratio
        )

        draw.line(
            [(0, y), (width, y)],
            fill=(r, g, b)
        )

    # --------------------------------------------------------
    # SUN
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # MOUNTAIN
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # TEXT PANEL
    # --------------------------------------------------------

    draw.rounded_rectangle(
        [65, 180, 1015, 870],
        radius=40,
        fill=(10, 20, 25)
    )

    # --------------------------------------------------------
    # HEADING
    # --------------------------------------------------------

    heading_font = get_font(
        48,
        bold=True
    )

    draw.text(
        (540, 245),
        "నేటి బైబిల్ వాక్యం",
        font=heading_font,
        anchor="mm",
        fill=(240, 200, 100)
    )

    # --------------------------------------------------------
    # VERSE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # REFERENCE
    # --------------------------------------------------------

    ref_font = get_font(
        43,
        bold=True
    )

    draw.text(
        (540, 790),
        verse_data["reference"],
        font=ref_font,
        anchor="mm",
        fill=(245, 190, 90)
    )

    # --------------------------------------------------------
    # BRANDING
    # --------------------------------------------------------

    brand_font = get_font(36)

    draw.text(
        (540, 1240),
        "తెలుగు క్రైస్తవుల కోసం ❤️",
        font=brand_font,
        anchor="mm",
        fill="white"
    )

    output = (
        DATA_DIR /
        "daily_bible_verse.jpg"
    )

    image.save(
        output,
        quality=95
    )

    return output


# ============================================================
# POST BIBLE VERSE
# ============================================================

def post_verse(history):

    data = generate_verse(
        history
    )

    image_path = create_bible_image(
        data
    )

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

    history["verses"] = (
        history["verses"][-200:]
    )

    save_history(
        history
    )

    print(
        "Bible verse posted successfully."
    )


# ============================================================
# POST BIBLE QUIZ
# ============================================================

def post_quiz(history):

    data = generate_quiz(
        history
    )

    validate_quiz(
        data
    )

    explanation = (
        f"📖 <b>బైబిల్ ఆధారం:</b> "
        f"{data['reference']}\n\n"
        f"💡 <b>వివరణ:</b> "
        f"{data['explanation']}\n\n"
        f"🙏 బైబిల్‌ను చదువుతూ మరింత తెలుసుకుందాం."
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

    history["quizzes"] = (
        history["quizzes"][-200:]
    )

    save_history(
        history
    )

    print(
        "Bible quiz posted successfully."
    )


# ============================================================
# POST BIBLE KNOWLEDGE QUIZ
# ============================================================

def post_knowledge(history):

    data = generate_knowledge(
        history
    )

    validate_quiz(
        data
    )

    explanation = (
        f"📖 <b>బైబిల్ ఆధారం:</b> "
        f"{data['reference']}\n\n"
        f"💡 <b>సమాధానం:</b> "
        f"{data['explanation']}\n\n"
        f"🙏 దేవుని వాక్యాన్ని మరింత తెలుసుకుందాం."
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

    history["knowledge"] = (
        history["knowledge"][-200:]
    )

    save_history(
        history
    )

    print(
        "Bible knowledge quiz posted successfully."
    )


# ============================================================
# QUIZ VALIDATION
# ============================================================

def validate_quiz(data):

    if not isinstance(
        data,
        dict
    ):

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

    # --------------------------------------------------------
    # QUESTION
    # --------------------------------------------------------

    if not isinstance(
        data["question"],
        str
    ):

        raise RuntimeError(
            "Quiz question must be text."
        )

    if not data["question"].strip():

        raise RuntimeError(
            "Quiz question is empty."
        )

    # --------------------------------------------------------
    # OPTIONS
    # --------------------------------------------------------

    options = data["options"]

    if not isinstance(
        options,
        list
    ):

        raise RuntimeError(
            "Quiz options must be a list."
        )

    if len(options) != 4:

        raise RuntimeError(
            "Quiz must have exactly 4 options."
        )

    for option in options:

        if not isinstance(
            option,
            str
        ):

            raise RuntimeError(
                "Each quiz option must be text."
            )

        if not option.strip():

            raise RuntimeError(
                "Quiz option cannot be empty."
