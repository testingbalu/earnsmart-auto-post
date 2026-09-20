import base64
import html
import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


# ============================================================
# CONFIGURATION
# ============================================================

HISTORY_FILE = os.environ.get(
    "BIBLE_HISTORY_FILE",
    "data/bible_history.json",
)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

GEMINI_API_BASE = (
    "https://generativelanguage.googleapis.com/v1beta"
)

TEXT_MODEL_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]

IMAGE_MODEL_CANDIDATES = [
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-exp",
]


# ============================================================
# ENVIRONMENT
# ============================================================

def require_env(name):
    value = os.environ.get(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value


GEMINI_API_KEY = require_env("GEMINI_API_KEY")
BOT_TOKEN = require_env("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = require_env("BIBLE_CHANNEL_ID")


# ============================================================
# HISTORY
# ============================================================

def empty_history():
    return {
        "verses": [],
        "quizzes": [],
        "knowledge": [],
    }


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return empty_history()

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        # New format:
        # {
        #   "verses": [],
        #   "quizzes": [],
        #   "knowledge": []
        # }
        if isinstance(data, dict):
            history = empty_history()

            for key in history:
                value = data.get(key, [])
                history[key] = value if isinstance(value, list) else []

            return history

        # Support the old list-based posting_history.json format.
        if isinstance(data, list):
            history = empty_history()

            for item in data:
                if not isinstance(item, dict):
                    continue

                post_type = item.get("type")

                if post_type in ("quote", "verse"):
                    history["verses"].append(item)

                elif post_type == "quiz":
                    history["quizzes"].append(item)

                elif post_type == "knowledge":
                    history["knowledge"].append(item)

            return history

    except Exception as error:
        print(f"WARNING: Could not load history: {error}")

    return empty_history()


def save_history(history):
    os.makedirs(os.path.dirname(HISTORY_FILE) or ".", exist_ok=True)

    try:
        cleaned = {
            "verses": history.get("verses", [])[-200:],
            "quizzes": history.get("quizzes", [])[-200:],
            "knowledge": history.get("knowledge", [])[-100:],
        }

        temporary_file = f"{HISTORY_FILE}.tmp"

        with open(temporary_file, "w", encoding="utf-8") as file:
            json.dump(
                cleaned,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(temporary_file, HISTORY_FILE)

    except Exception as error:
        raise RuntimeError(
            f"Could not save posting history: {error}"
        ) from error


def normalize_text(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip(),
    ).casefold()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# GEMINI MODEL HELPERS
# ============================================================

def get_available_models():
    try:
        response = requests.get(
            f"{GEMINI_API_BASE}/models",
            headers={"x-goog-api-key": GEMINI_API_KEY},
            timeout=30,
        )

        if not response.ok:
            print(
                "WARNING: Gemini model discovery failed: "
                f"HTTP {response.status_code}"
            )
            return {}

        data = response.json()
        models = {}

        for item in data.get("models", []):
            name = str(item.get("name", ""))

            if name.startswith("models/"):
                name = name[len("models/"):]

            models[name] = item.get(
                "supportedGenerationMethods",
                [],
            )

        return models

    except Exception as error:
        print(f"WARNING: Gemini model discovery failed: {error}")
        return {}


def choose_model(candidates, available, environment_name):
    custom = os.environ.get(environment_name, "").strip()

    if custom:
        if not available or custom in available:
            return custom

        print(
            f"WARNING: {environment_name}={custom} "
            "is not available."
        )

    for model in candidates:
        methods = available.get(model, [])

        if not available or "generateContent" in methods:
            return model

    raise RuntimeError(
        f"No usable Gemini model found for {environment_name}."
    )


def clean_json_text(text):
    text = str(text).strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"^```\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    return text.strip()


def extract_gemini_text(body, model):
    if not isinstance(body, dict):
        raise RuntimeError(f"{model}: Invalid Gemini response.")

    if "error" in body:
        error = body["error"]

        if isinstance(error, dict):
            message = error.get("message", str(error))
        else:
            message = str(error)

        raise RuntimeError(f"{model}: {message}")

    candidates = body.get("candidates", [])

    if not candidates:
        raise RuntimeError(f"{model}: No candidates returned.")

    texts = []

    for candidate in candidates:
        content = candidate.get("content", {})

        for part in content.get("parts", []):
            text = part.get("text")

            if isinstance(text, str) and text.strip():
                texts.append(text)

    if not texts:
        raise RuntimeError(f"{model}: No text returned.")

    return "\n".join(texts).strip()


def gemini_json(prompt):
    available = get_available_models()
    primary = choose_model(
        TEXT_MODEL_CANDIDATES,
        available,
        "GEMINI_MODEL",
    )

    models = [primary]

    for model in TEXT_MODEL_CANDIDATES:
        if model not in models:
            models.append(model)

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt,
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json",
        },
    }

    last_error = None

    for model in models:
        methods = available.get(model, [])

        if available and "generateContent" not in methods:
            continue

        url = (
            f"{GEMINI_API_BASE}/models/"
            f"{model}:generateContent"
        )

        for attempt in range(3):
            try:
                response = requests.post(
                    url,
                    headers={
                        "x-goog-api-key": GEMINI_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=90,
                )

                if response.ok:
                    body = response.json()
                    text = extract_gemini_text(body, model)
                    return json.loads(clean_json_text(text))

                if (
                    response.status_code
                    not in RETRYABLE_STATUS_CODES
                ):
                    raise RuntimeError(
                        f"{model}: HTTP {response.status_code}: "
                        f"{response.text[:1000]}"
                    )

                delay = min(60, 5 * (2 ** attempt))
                delay += random.uniform(0, 2)

                print(
                    f"Gemini temporary error "
                    f"{response.status_code}; retrying in "
                    f"{delay:.1f}s"
                )

                time.sleep(delay)

            except Exception as error:
                last_error = error

                if attempt == 2:
                    break

                time.sleep(3 + random.uniform(0, 2))

        print(f"Gemini model {model} failed: {last_error}")

    raise RuntimeError(
        f"All Gemini text models failed: {last_error}"
    )


# ============================================================
# VERSE GENERATION
# ============================================================

def verse_key(item):
    text = normalize_text(item.get("text"))
    reference = normalize_text(item.get("reference"))
    return f"{text}|{reference}"


def generate_quote(history):
    used = history.get("verses", [])

    previous = [
        {
            "text": item.get("text", ""),
            "reference": item.get("reference", ""),
        }
        for item in used
        if item.get("text")
    ]

    used_keys = {
        verse_key(item)
        for item in used
    }

    for attempt in range(8):
        prompt = f"""
"Telugu Christians world" అనే తెలుగు క్రైస్తవ
Telegram channel కోసం ఒక Bible verse post తయారు చేయండి.

నియమాలు:
1. నిజమైన Bible verse మాత్రమే ఉపయోగించండి.
2. Bible reference ఖచ్చితంగా సరైనదిగా ఉండాలి.
3. పాత verse లేదా అదే reference ను మళ్లీ ఉపయోగించవద్దు.
4. ఇప్పటికే ఉపయోగించిన verse కు చాలా దగ్గరగా ఉన్న verse కూడా వద్దు.
5. సహజమైన తెలుగు ఉపయోగించండి.
6. JSON మాత్రమే ఇవ్వండి.

ఇప్పటికే ఉపయోగించిన verses:
{json.dumps(previous[-100:], ensure_ascii=False)}

JSON format:
{{
  "text": "తెలుగు బైబిల్ వాక్యం",
  "reference": "గ్రంథం అధ్యాయం:వచనం",
  "reflection": "ఈ వాక్యం మన జీవితానికి చెప్పే చిన్న ఆలోచన"
}}
"""

        data = gemini_json(prompt)

        if not isinstance(data, dict):
            continue

        item = {
            "text": str(data.get("text", "")).strip(),
            "reference": str(data.get("reference", "")).strip(),
            "reflection": str(data.get("reflection", "")).strip(),
        }

        key = verse_key(item)

        if (
            item["text"]
            and item["reference"]
            and item["reflection"]
            and key not in used_keys
        ):
            return item

        print(
            f"Rejected duplicate or invalid verse "
            f"attempt {attempt + 1}/8"
        )

    raise RuntimeError(
        "Could not generate a unique Bible verse."
    )


# ============================================================
# IMAGE GENERATION
# ============================================================

def generate_ai_background(quote, reference, reflection):
    available = get_available_models()

    model = choose_model(
        IMAGE_MODEL_CANDIDATES,
        available,
        "GEMINI_IMAGE_MODEL",
    )

    prompt = f"""
Create a beautiful bright Christian Bible illustration
for a Telugu Bible verse card.

VERSE:
{quote}

REFERENCE:
{reference}

MEANING:
{reflection}

Style:
- Bright
- Warm
- Peaceful
- Uplifting
- Soft sunlight
- Blue sky
- Gentle clouds
- Greenery
- Natural pastel colors
- Dignified depiction of Jesus
- Historically inspired clothing

Composition:
- Portrait 4:5 composition
- Keep the upper third clean
- Keep important subjects toward the lower or side areas
- Leave clean space for Telugu text added later

Do not include:
- Telugu letters
- English letters
- Any text
- Logos
- Watermarks
- Signatures
- Labels
- Dark horror mood
- Heavy black background
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt,
                    }
                ],
            }
        ],
        "generationConfig": {
            "responseModalities": [
                "TEXT",
                "IMAGE",
            ],
        },
    }

    response = requests.post(
        (
            f"{GEMINI_API_BASE}/models/"
            f"{model}:generateContent"
        ),
        headers={
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=180,
    )

    if not response.ok:
        raise RuntimeError(
            f"{model}: HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    body = response.json()

    if "error" in body:
        raise RuntimeError(str(body["error"]))

    for candidate in body.get("candidates", []):
        parts = candidate.get("content", {}).get("parts", [])

        for part in parts:
            # Gemini may return either spelling depending on API version.
            inline_data = (
                part.get("inlineData")
                or part.get("inline_data")
            )

            if not inline_data:
                continue

            encoded = inline_data.get("data")

            if not encoded:
                continue

            try:
                image_bytes = base64.b64decode(
                    encoded,
                    validate=True,
                )

                image = Image.open(
                    BytesIO(image_bytes)
                )

                image.load()
                return image.convert("RGB")

            except Exception as error:
                raise RuntimeError(
                    f"Invalid generated image: {error}"
                ) from error

    raise RuntimeError(
        f"{model}: No image data returned."
    )


def fallback_background():
    image = Image.new(
        "RGB",
        (1080, 1350),
        (210, 238, 255),
    )

    draw = ImageDraw.Draw(image)

    for y in range(image.height):
        ratio = y / image.height

        color = (
            int(205 + 35 * ratio),
            int(235 + 12 * ratio),
            int(255 - 15 * ratio),
        )

        draw.line(
            (0, y, image.width, y),
            fill=color,
        )

    draw.ellipse(
        (780, 80, 980, 280),
        fill=(255, 244, 170),
    )

    draw.ellipse(
        (0, 850, 1150, 1500),
        fill=(181, 224, 157),
    )

    draw.ellipse(
        (120, 1000, 650, 1500),
        fill=(151, 205, 130),
    )

    return image


# ============================================================
# QUOTE IMAGE
# ============================================================

def find_telugu_font():
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansTelugu-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansTeluguUI-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSerifTelugu-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansTelugu-Regular.ttf",
        "/usr/share/fonts/truetype/lohit-telugu/Lohit-Telugu.ttf",
        "/usr/share/fonts/truetype/telugufonts/Telugu-Regular.ttf",
        "/usr/share/fonts/truetype/telugu/Telugu-Regular.ttf",
    ]

    for path in candidates:
        if os.path.exists(path):
            return path

    for root, _, files in os.walk("/usr/share/fonts"):
        for name in files:
            lower = name.lower()

            if (
                "telugu" in lower
                and lower.endswith((".ttf", ".otf", ".ttc"))
            ):
                return os.path.join(root, name)

    for root, _, files in os.walk("/usr/local/share/fonts"):
        for name in files:
            lower = name.lower()

            if (
                "telugu" in lower
                and lower.endswith((".ttf", ".otf", ".ttc"))
            ):
                return os.path.join(root, name)

    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{file}\n", "Noto Sans Telugu"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            path = result.stdout.strip().splitlines()[0].strip()
            if path and os.path.exists(path):
                return path
    except Exception:
        pass

    for fallback in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]:
        if os.path.exists(fallback):
            return fallback

    raise FileNotFoundError(
        "Telugu font not found. Install fonts-noto-core or fonts-noto-extra."
    )


def wrap_text(draw, text, font, max_width):
    lines = []
    current = ""

    for word in str(text).split():
        candidate = f"{current} {word}".strip()

        box = draw.textbbox(
            (0, 0),
            candidate,
            font=font,
        )

        if box[2] - box[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    return lines


def make_quote_image(
    text,
    reference,
    reflection,
    output="quote_card.png",
):
    try:
        background = generate_ai_background(
            text,
            reference,
            reflection,
        )

    except Exception as error:
        print(f"WARNING: AI image failed: {error}")
        print("Using fallback background.")
        background = fallback_background()

    background = background.convert("RGB")

    target_ratio = 4 / 5
    source_ratio = background.width / background.height

    if source_ratio > target_ratio:
        crop_height = background.height
        crop_width = int(crop_height * target_ratio)
    else:
        crop_width = background.width
        crop_height = int(crop_width / target_ratio)

    left = (background.width - crop_width) // 2
    top = (background.height - crop_height) // 2

    image = background.crop(
        (
            left,
            top,
            left + crop_width,
            top + crop_height,
        )
    )

    image = image.resize(
        (1080, 1350),
        Image.Resampling.LANCZOS,
    )

    image = ImageEnhance.Color(image).enhance(1.08)
    image = ImageEnhance.Brightness(image).enhance(1.04)
    image = image.filter(
        ImageFilter.GaussianBlur(0.25)
    ).convert("RGBA")

    font_path = find_telugu_font()

    title_font = ImageFont.truetype(font_path, 42)
    verse_font = ImageFont.truetype(font_path, 50)
    reference_font = ImageFont.truetype(font_path, 38)
    footer_font = ImageFont.truetype(font_path, 28)

    card = Image.new(
        "RGBA",
        image.size,
        (0, 0, 0, 0),
    )

    card_draw = ImageDraw.Draw(card)

    card_draw.rounded_rectangle(
        (42, 48, 1038, 650),
        radius=42,
        fill=(255, 255, 255, 150),
        outline=(255, 255, 255, 220),
        width=4,
    )

    image = Image.alpha_composite(image, card)
    draw = ImageDraw.Draw(image)

    text_fill = (224, 32, 32, 255)
    white_stroke = (255, 255, 255, 255)

    draw.text(
        (540, 115),
        "నేటి బైబిల్ వాక్యం",
        font=title_font,
        fill=text_fill,
        stroke_width=9,
        stroke_fill=white_stroke,
        anchor="mm",
    )

    lines = wrap_text(
        draw,
        text,
        verse_font,
        860,
    )[:6]

    line_height = 78
    start_y = 330 - (
        (len(lines) - 1) * line_height / 2
    )

    for index, line in enumerate(lines):
        draw.text(
            (
                540,
                start_y + index * line_height,
            ),
            line,
            font=verse_font,
            fill=text_fill,
            stroke_width=8,
            stroke_fill=white_stroke,
            anchor="mm",
        )

    draw.text(
        (540, 585),
        reference,
        font=reference_font,
        fill=text_fill,
        stroke_width=8,
        stroke_fill=white_stroke,
        anchor="mm",
    )

    draw.text(
        (540, 1290),
        "Telugu Christians world",
        font=footer_font,
        fill=(255, 255, 255, 255),
        stroke_width=3,
        stroke_fill=(105, 75, 45, 180),
        anchor="mm",
    )

    image.convert("RGB").save(
        output,
        "PNG",
        optimize=True,
    )

    return output


# ============================================================
# TELEGRAM
# ============================================================

def telegram_url(method):
    return (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/{method}"
    )


def telegram_response_check(response, method):
    if not response.ok:
        raise RuntimeError(
            f"Telegram {method} failed: "
            f"HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    try:
        result = response.json()
    except Exception as error:
        raise RuntimeError(
            f"Telegram {method} returned invalid JSON."
        ) from error

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram {method} API error: {result}"
        )

    return result


def post_quote(data):
    quote = html.escape(data["text"])
    reference = html.escape(data["reference"])
    reflection = html.escape(data["reflection"])

    caption = (
        "<b>📖 నేటి బైబిల్ వాక్యం</b>\n\n"
        f"\"{quote}\"\n\n"
        f"📍 <b>{reference}</b>\n\n"
        f"💭 {reflection}"
    )

    # Telegram sendPhoto captions cannot exceed 1024 characters.
    caption = caption[:1024]

    try:
        image_path = make_quote_image(
            data["text"],
            data["reference"],
            data["reflection"],
        )

        with open(image_path, "rb") as image_file:
            response = requests.post(
                telegram_url("sendPhoto"),
                files={"photo": image_file},
                data={
                    "chat_id": CHANNEL_ID,
                    "caption": caption,
                    "parse_mode": "HTML",
                },
                timeout=60,
            )

        return telegram_response_check(response, "sendPhoto")

    except Exception as error:
        print(f"WARNING: Verse image posting failed; sending text fallback: {error}")
        response = requests.post(
            telegram_url("sendMessage"),
            json={
                "chat_id": CHANNEL_ID,
                "text": caption,
                "parse_mode": "HTML",
            },
            timeout=60,
        )
        return telegram_response_check(response, "sendMessage")


# ============================================================
# QUIZ
# ============================================================

def quiz_key(question):
    return normalize_text(question)


def generate_quiz(history):
    used = history.get("quizzes", [])

    previous = [
        str(item.get("question", "")).strip()
        for item in used
        if item.get("question")
    ]

    used_keys = {
        quiz_key(question)
        for question in previous
    }

    for attempt in range(8):
        prompt = f"""
"Telugu Christians world" కోసం ఒక తెలుగు Bible quiz తయారు చేయండి.

నియమాలు:
1. నిజమైన Bible information మాత్రమే ఉపయోగించండి.
2. పాత ప్రశ్నను లేదా అదే ప్రశ్నను మళ్లీ ఉపయోగించవద్దు.
3. EXACTLY 4 options ఉండాలి.
4. answer_index 0, 1, 2 లేదా 3 మాత్రమే.
5. explanation చిన్నదిగా ఉండాలి.
6. reference సరైన Bible reference అయి ఉండాలి.
7. JSON మాత్రమే ఇవ్వండి.

ఇప్పటికే ఉపయోగించిన ప్రశ్నలు:
{json.dumps(previous[-100:], ensure_ascii=False)}

JSON:
{{
  "question": "ప్రశ్న",
  "options": [
    "ఆప్షన్ 1",
    "ఆప్షన్ 2",
    "ఆప్షన్ 3",
    "ఆప్షన్ 4"
  ],
  "answer_index": 0,
  "explanation": "సమాధానం వివరణ",
  "reference": "గ్రంథం అధ్యాయం:వచనం"
}}
"""

        data = gemini_json(prompt)

        if not isinstance(data, dict):
            continue

        question = str(
            data.get("question", "")
        ).strip()

        options = data.get("options")
        explanation = str(
            data.get("explanation", "")
        ).strip()

        reference = str(
            data.get("reference", "")
        ).strip()

        try:
            answer_index = int(data.get("answer_index"))
        except Exception:
            answer_index = -1

        if not question:
            continue

        if (
            not isinstance(options, list)
            or len(options) != 4
        ):
            continue

        options = [
            str(option).strip()
            for option in options
        ]

        if any(not option for option in options):
            continue

        if len({normalize_text(option) for option in options}) != 4:
            continue

        if answer_index not in range(4):
            continue

        key = quiz_key(question)

        if key in used_keys:
            print(
                f"Rejected duplicate quiz "
                f"attempt {attempt + 1}/8"
            )
            continue

        if not reference:
            print(
                f"Rejected invalid quiz reference "
                f"attempt {attempt + 1}/8"
            )
            continue

        return {
            "question": question,
            "options": options,
            "answer_index": answer_index,
            "explanation": explanation,
            "reference": reference,
        }

    raise RuntimeError(
        "Could not generate a unique Bible quiz."
    )


def post_quiz(data):
    explanation = data.get("explanation", "")
    explanation = str(explanation)[:200]

    response = requests.post(
        telegram_url("sendPoll"),
        json={
            "chat_id": CHANNEL_ID,
            "question": data["question"],
            "options": data["options"],
            "type": "quiz",
            "correct_option_id": data["answer_index"],
            "is_anonymous": True,
            "explanation": explanation,
        },
        timeout=60,
    )

    return telegram_response_check(response, "sendPoll")


# ============================================================
# KNOWLEDGE
# ============================================================

def generate_knowledge(history):
    used = history.get("knowledge", [])

    previous = [
        str(item.get("title", "")).strip()
        for item in used
        if isinstance(item, dict) and item.get("title")
    ]

    prompt = f"""
"Telugu Christians world" కోసం ఉపయోగకరమైన తెలుగు
Bible knowledge post తయారు చేయండి.

నియమాలు:
1. నిజమైన Bible information మాత్రమే.
2. పాత topic లేదా title పునరావృతం చేయవద్దు.
3. కనీసం 3 ముఖ్యమైన points ఇవ్వండి.
4. సహజమైన తెలుగు ఉపయోగించండి.
5. JSON మాత్రమే ఇవ్వండి.

ఇటీవల ఉపయోగించిన topics:
{json.dumps(previous[-100:], ensure_ascii=False)}

JSON:
{{
  "title": "శీర్షిక",
  "content": "కనీసం 3 ముఖ్యమైన points",
  "reference": "సంబంధిత Bible reference"
}}
"""

    data = gemini_json(prompt)

    if not isinstance(data, dict):
        raise RuntimeError("Invalid knowledge response.")

    result = {
        "title": str(data.get("title", "")).strip(),
        "content": str(data.get("content", "")).strip(),
        "reference": str(data.get("reference", "")).strip(),
    }

    if not result["title"]:
        raise RuntimeError("Knowledge title is empty.")

    if not result["content"]:
        raise RuntimeError("Knowledge content is empty.")

    old_titles = {
        normalize_text(title)
        for title in previous
    }

    if normalize_text(result["title"]) in old_titles:
        raise RuntimeError(
            "Gemini returned a duplicate knowledge topic."
        )

    return result


def post_knowledge(data):
    title = html.escape(data["title"])
    content = html.escape(data["content"])
    reference = html.escape(data["reference"])

    message = (
        "<b>💡 నేటి బైబిల్ జ్ఞానం</b>\n\n"
        f"<b>{title}</b>\n\n"
        f"{content}\n\n"
        f"📍 {reference}"
    )

    response = requests.post(
        telegram_url("sendMessage"),
        json={
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "HTML",
        },
        timeout=60,
    )

    return telegram_response_check(response, "sendMessage")


# ============================================================
# MAIN
# ============================================================

def main():
    history = load_history()

    post_type = os.environ.get(
        "POST_TYPE",
        "quote",
    ).strip().lower()

    # The workflow uses verse_quiz only as a wrapper. The actual
    # two executions use POST_TYPE=quote and POST_TYPE=quiz.
    if post_type == "verse":
        post_type = "quote"

    if post_type == "verse_quiz":
        raise RuntimeError(
            "Use POST_TYPE=quote followed by POST_TYPE=quiz "
            "for a verse-and-quiz slot."
        )

    print("=" * 60)
    print("TELUGU CHRISTIANS WORLD - BIBLE BOT")
    print(f"Post type: {post_type}")
    print(f"History file: {HISTORY_FILE}")
    print("=" * 60)

    try:
        if post_type == "quote":
            data = generate_quote(history)

            print(f"Verse reference: {data['reference']}")
            post_quote(data)

            history["verses"].append(
                {
                    **data,
                    "timestamp": now_iso(),
                }
            )

        elif post_type == "quiz":
            data = generate_quiz(history)

            print(f"Quiz: {data['question']}")
            post_quiz(data)

            history["quizzes"].append(
                {
                    **data,
                    "timestamp": now_iso(),
                }
            )

        elif post_type == "knowledge":
            data = generate_knowledge(history)

            print(f"Knowledge: {data['title']}")
            post_knowledge(data)

            history["knowledge"].append(
                {
                    **data,
                    "timestamp": now_iso(),
                }
            )

        else:
            raise ValueError(
                f"Unknown POST_TYPE={post_type}. "
                "Use quote, quiz, or knowledge."
            )

        # Save only after Telegram succeeds.
        save_history(history)

        print("=" * 60)
        print(f"SUCCESS: {post_type} posted")
        print("=" * 60)

    except Exception as error:
        print("=" * 60)
        print(f"ERROR: {error}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
