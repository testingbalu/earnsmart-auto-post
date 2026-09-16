import os
import json
import re
import sys
import base64
import random
import time
import html
from datetime import datetime, timezone
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter


# ============================================================
# CONFIGURATION
# ============================================================

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

HISTORY_FILE = "posting_history.json"


def require_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )
    return value.strip()


GEMINI_API_KEY = require_env("GEMINI_API_KEY")
BOT_TOKEN = require_env("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = require_env("BIBLE_CHANNEL_ID")


# Current stable text model.
# Can be overridden through GitHub Secrets/Variables.
GEMINI_MODELS = [
    os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite"),
]


# Current image generation model.
IMAGE_MODELS = [
    os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
]


# ============================================================
# HISTORY
# ============================================================

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except Exception as exc:
        print(f"WARNING: Could not load history: {exc}")
        return []


def save_history(history):
    try:
        with open(
            HISTORY_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                history[-100:],
                file,
                ensure_ascii=False,
                indent=2
            )
    except Exception as exc:
        print(f"WARNING: Could not save history: {exc}")


# ============================================================
# GEMINI RESPONSE HELPERS
# ============================================================

def extract_text_from_gemini_response(body, model_name):

    if not isinstance(body, dict):
        raise ValueError(
            f"{model_name}: Gemini returned non-JSON payload"
        )

    if "error" in body:
        error = body.get("error")

        if isinstance(error, dict):
            message = error.get(
                "message",
                str(error)
            )
        else:
            message = str(error)

        raise RuntimeError(
            f"{model_name}: Gemini API error: {message}"
        )

    candidates = body.get("candidates")

    if not isinstance(candidates, list) or not candidates:
        raise ValueError(
            f"{model_name}: Gemini returned no candidates: "
            f"{body}"
        )

    candidate = candidates[0]

    if not isinstance(candidate, dict):
        raise ValueError(
            f"{model_name}: Invalid candidate format"
        )

    content = candidate.get("content")

    if not isinstance(content, dict):
        raise ValueError(
            f"{model_name}: Candidate has no content"
        )

    parts = content.get("parts")

    if not isinstance(parts, list):
        raise ValueError(
            f"{model_name}: Candidate has no parts"
        )

    text_parts = []

    for part in parts:

        if not isinstance(part, dict):
            continue

        text = part.get("text")

        if isinstance(text, str) and text.strip():
            text_parts.append(text.strip())

    if not text_parts:
        raise ValueError(
            f"{model_name}: No text found in Gemini response"
        )

    return "\n".join(text_parts).strip()


def clean_json_text(text):

    text = text.strip()

    # Remove markdown JSON fences.
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


# ============================================================
# GEMINI TEXT API
# ============================================================

def call_gemini_json(model, payload):

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    for attempt in range(5):

        try:

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=90
            )

            # -------------------------------
            # SUCCESS
            # -------------------------------

            if response.ok:

                try:
                    body = response.json()

                except ValueError as exc:

                    raise RuntimeError(
                        f"{model}: Invalid JSON response: "
                        f"{response.text[:800]}"
                    ) from exc

                text = extract_text_from_gemini_response(
                    body,
                    model
                )

                text = clean_json_text(text)

                try:
                    return json.loads(text)

                except json.JSONDecodeError as exc:

                    raise RuntimeError(
                        f"{model}: Gemini returned invalid JSON:\n"
                        f"{text[:1500]}"
                    ) from exc

            # -------------------------------
            # PERMANENT ERROR
            # -------------------------------

            if response.status_code not in RETRYABLE_STATUS_CODES:

                raise RuntimeError(
                    f"{model}: HTTP {response.status_code}: "
                    f"{response.text[:1000]}"
                )

            # -------------------------------
            # RETRYABLE ERROR
            # -------------------------------

            delay = (
                min(60, 2 ** attempt * 5)
                + random.uniform(0, 2)
            )

            print(
                f"Gemini {model} returned "
                f"{response.status_code}. "
                f"Retrying in {delay:.1f}s..."
            )

            time.sleep(delay)

        except RuntimeError:
            raise

        except requests.RequestException as exc:

            if attempt == 4:
                raise RuntimeError(
                    f"{model}: Network error: {exc}"
                ) from exc

            delay = (
                min(60, 2 ** attempt * 5)
                + random.uniform(0, 2)
            )

            print(
                f"Gemini network error: {exc}. "
                f"Retrying in {delay:.1f}s..."
            )

            time.sleep(delay)

    raise RuntimeError(
        f"Gemini API exhausted retries for {model}"
    )


def gemini(prompt):

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],

        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json",
        },
    }

    last_error = None

    for model in GEMINI_MODELS:

        if not model:
            continue

        try:

            print(f"Using Gemini text model: {model}")

            return call_gemini_json(
                model,
                payload
            )

        except Exception as exc:

            last_error = str(exc)

            print(
                f"Gemini text model {model} failed: "
                f"{exc}"
            )

    raise RuntimeError(
        f"All Gemini text models failed: {last_error}"
    )


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(value):

    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip()
    ).casefold()


# ============================================================
# QUOTE GENERATION
# ============================================================

def used_quotes(history):

    return {
        normalize_text(item.get("text"))
        for item in history
        if item.get("type") in ("quote", "verse")
        and normalize_text(item.get("text"))
    }


def generate_quote(history):

    previous = [
        item.get("text", "")
        for item in history
        if item.get("type") in ("quote", "verse")
        and item.get("text")
    ]

    rejected = used_quotes(history)

    # Only send recent history to Gemini.
    previous_recent = previous[-40:]

    for attempt in range(8):

        prompt = f"""
మీరు "Telugu Christians world" అనే తెలుగు క్రైస్తవ
టెలిగ్రామ్ ఛానల్ కోసం ఒక Bible verse post తయారు చేస్తున్నారు.

ముఖ్యమైన నియమాలు:

1. నిజమైన బైబిల్ వాక్యాన్ని మాత్రమే ఉపయోగించండి.
2. మీకు ఖచ్చితంగా తెలిసిన Bible reference మాత్రమే ఇవ్వండి.
3. ఇప్పటికే ఉపయోగించిన వాక్యాన్ని మళ్లీ ఉపయోగించవద్దు.
4. ఇప్పటికే ఉన్న వాక్యానికి చాలా దగ్గరగా ఉన్న వాక్యాన్ని కూడా
   ఉపయోగించవద్దు.
5. సహజమైన తెలుగు ఉపయోగించండి.
6. JSON మాత్రమే ఇవ్వండి.

ఇప్పటికే ఉపయోగించిన వాక్యాలు:

{json.dumps(previous_recent, ensure_ascii=False)}

JSON format:

{{
  "text": "తెలుగులో బైబిల్ వాక్యం",
  "reference": "గ్రంథం అధ్యాయం:వచనం",
  "reflection": "ఈ వాక్యం మన జీవితానికి చెప్పే చిన్న ఉపయోగకరమైన ఆలోచన"
}}
"""

        data = gemini(prompt)

        if not isinstance(data, dict):
            print("Invalid quote response.")
            continue

        text = str(
            data.get("text", "")
        ).strip()

        reference = str(
            data.get("reference", "")
        ).strip()

        reflection = str(
            data.get("reflection", "")
        ).strip()

        key = normalize_text(text)

        if (
            text
            and reference
            and reflection
            and key not in rejected
        ):

            return {
                "text": text,
                "reference": reference,
                "reflection": reflection,
            }

        print(
            f"Duplicate/invalid quote rejected "
            f"(attempt {attempt + 1})"
        )

        if text:
            previous.append(text)
            rejected.add(key)

    raise RuntimeError(
        "Could not generate a unique Bible quote."
    )


# ============================================================
# GEMINI IMAGE GENERATION
# ============================================================

def generate_ai_background(
    quote,
    reference,
    reflection
):

    prompt = f"""
Create a beautiful bright Christian Bible illustration
for a Telugu Bible verse card.

Verse:
{quote}

Reference:
{reference}

Meaning:
{reflection}

VISUAL DIRECTION:

- Create the visual scene based on the meaning of the verse.
- Comfort/protection: peaceful protective scene.
- Hope: sunrise/light.
- Strength: Jesus helping or encouraging someone.
- Prayer: peaceful prayer scene.
- Guidance: path with Jesus walking beside a person.
- Forgiveness: reconciliation.
- Healing: comforting healing scene.
- Love/kindness: warm family/community scene.

Style:

- Bright
- Warm
- Peaceful
- Uplifting
- Christian devotional greeting-card style
- Soft sunlight
- Blue sky
- Gentle clouds
- Greenery
- Flowers where appropriate
- Natural pastel colors
- Compassionate and dignified depiction of Jesus
- Historically inspired clothing

COMPOSITION:

- Portrait / vertical composition.
- Prefer 4:5 aspect ratio.
- Keep the upper portion relatively clean and bright.
- Keep the main visual subject toward the lower or side portion.
- Leave enough clean space for Telugu text to be added later.

DO NOT generate:

- Telugu text
- English text
- Bible verses
- Logos
- Signatures
- Watermarks
- Labels
- Black background
- Horror mood
- Dark cinematic mood
- Heavy vignette
"""

    last_error = None

    for model in IMAGE_MODELS:

        if not model:
            continue

        print(
            f"Using Gemini image model: {model}"
        )

        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{model}:generateContent"
        )

        headers = {
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        }

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],

            "generationConfig": {
                "responseModalities": [
                    "TEXT",
                    "IMAGE"
                ],

                "responseFormat": {
                    "image": {
                        "aspectRatio": "4:5"
                    }
                }
            }
        }

        for attempt in range(5):

            try:

                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=180
                )

                if response.ok:

                    body = response.json()

                    if "error" in body:
                        raise RuntimeError(
                            str(body["error"])
                        )

                    candidates = body.get(
                        "candidates",
                        []
                    )

                    for candidate in candidates:

                        content = candidate.get(
                            "content",
                            {}
                        )

                        parts = content.get(
                            "parts",
                            []
                        )

                        for part in parts:

                            inline_data = (
                                part.get("inlineData")
                            )

                            if not inline_data:
                                continue

                            encoded = (
                                inline_data.get("data")
                            )

                            if not encoded:
                                continue

                            try:

                                image_bytes = base64.b64decode(
                                    encoded,
                                    validate=True
                                )

                                image = Image.open(
                                    BytesIO(image_bytes)
                                )

                                image.load()

                                return image.convert(
                                    "RGB"
                                )

                            except Exception as exc:

                                raise RuntimeError(
                                    f"Invalid generated image: "
                                    f"{exc}"
                                ) from exc

                    raise RuntimeError(
                        f"{model}: Gemini returned "
                        "no image data."
                    )

                if (
                    response.status_code
                    not in RETRYABLE_STATUS_CODES
                ):

                    raise RuntimeError(
                        f"{model}: HTTP "
                        f"{response.status_code}: "
                        f"{response.text[:1000]}"
                    )

                delay = (
                    min(60, 2 ** attempt * 5)
                    + random.uniform(0, 2)
                )

                print(
                    f"Gemini image temporary error "
                    f"{response.status_code}. "
                    f"Retrying in {delay:.1f}s..."
                )

                time.sleep(delay)

            except RuntimeError:
                raise

            except requests.RequestException as exc:

                if attempt == 4:
                    raise RuntimeError(
                        f"{model}: Network error: {exc}"
                    ) from exc

                delay = (
                    min(60, 2 ** attempt * 5)
                    + random.uniform(0, 2)
                )

                print(
                    f"Gemini image network error: "
                    f"{exc}. "
                    f"Retrying in {delay:.1f}s..."
                )

                time.sleep(delay)

            except Exception as exc:

                last_error = str(exc)

                if attempt == 4:
                    break

                delay = (
                    min(60, 2 ** attempt * 5)
                    + random.uniform(0, 2)
                )

                print(
                    f"Gemini image error: {exc}. "
                    f"Retrying in {delay:.1f}s..."
                )

                time.sleep(delay)

        print(
            f"Image model {model} failed: "
            f"{last_error}"
        )

    raise RuntimeError(
        f"Gemini image generation failed: "
        f"{last_error}"
    )


# ============================================================
# FALLBACK BACKGROUND
# ============================================================

def fallback_background():

    image = Image.new(
        "RGB",
        (1080, 1350),
        (211, 239, 255)
    )

    draw = ImageDraw.Draw(image)

    for y in range(1350):

        t = y / 1350

        r = int(205 + 35 * t)
        g = int(235 + 12 * t)
        b = int(255 - 15 * t)

        draw.line(
            (0, y, 1080, y),
            fill=(r, g, b)
        )

    draw.ellipse(
        (780, 80, 980, 280),
        fill=(255, 244, 170)
    )

    draw.ellipse(
        (0, 850, 1150, 1500),
        fill=(181, 224, 157)
    )

    draw.ellipse(
        (120, 1000, 650, 1500),
        fill=(151, 205, 130)
    )

    return image


# ============================================================
# TELUGU FONT
# ============================================================

def find_telugu_font():

    possible_paths = [

        "/usr/share/fonts/truetype/noto/"
        "NotoSansTelugu-Regular.ttf",

        "/usr/share/fonts/opentype/noto/"
        "NotoSansTelugu-Regular.ttf",

        "/usr/share/fonts/truetype/lohit-telugu/"
        "Lohit-Telugu.ttf",

    ]

    for path in possible_paths:

        if os.path.exists(path):
            return path

    # Search entire font directory.
    for root, _, files in os.walk(
        "/usr/share/fonts"
    ):

        for name in files:

            if (
                "telugu" in name.lower()
                and name.lower().endswith(
                    (".ttf", ".otf")
                )
            ):

                return os.path.join(
                    root,
                    name
                )

    raise FileNotFoundError(
        "Telugu font not found. "
        "Install Noto Sans Telugu."
    )


# ============================================================
# TEXT WRAPPING
# ============================================================

def wrap_text(
    draw,
    text,
    font,
    max_width
):

    lines = []
    current = ""

    for word in str(text).split():

        candidate = (
            f"{current} {word}"
        ).strip()

        bbox = draw.textbbox(
            (0, 0),
            candidate,
            font=font
        )

        width = bbox[2] - bbox[0]

        if width <= max_width:

            current = candidate

        else:

            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    return lines


# ============================================================
# CREATE QUOTE IMAGE
# ============================================================

def make_quote_image(
    text,
    reference,
    reflection,
    output="quote_card.png"
):

    try:

        background = generate_ai_background(
            text,
            reference,
            reflection
        )

    except Exception as error:

        print(
            "WARNING: AI image generation failed: "
            f"{error}"
        )

        print(
            "Using fallback background."
        )

        background = fallback_background()

    background = background.convert("RGB")

    target_ratio = 4 / 5

    source_ratio = (
        background.width /
        background.height
    )

    if source_ratio > target_ratio:

        new_height = background.height

        new_width = int(
            new_height * target_ratio
        )

    else:

        new_width = background.width

        new_height = int(
            new_width / target_ratio
        )

    left = (
        background.width -
        new_width
    ) // 2

    top = (
        background.height -
        new_height
    ) // 2

    image = background.crop(
        (
            left,
            top,
            left + new_width,
            top + new_height
        )
    ).resize(
        (1080, 1350),
        Image.Resampling.LANCZOS
    )

    image = ImageEnhance.Color(
        image
    ).enhance(1.08)

    image = ImageEnhance.Brightness(
        image
    ).enhance(1.04)

    image = image.filter(
        ImageFilter.GaussianBlur(0.25)
    ).convert("RGBA")

    font_path = find_telugu_font()

    title_font = ImageFont.truetype(
        font_path,
        42
    )

    verse_font = ImageFont.truetype(
        font_path,
        50
    )

    reference_font = ImageFont.truetype(
        font_path,
        38
    )

    footer_font = ImageFont.truetype(
        font_path,
        28
    )

    # --------------------------------------------
    # WHITE TRANSPARENT CARD
    # --------------------------------------------

    card = Image.new(
        "RGBA",
        image.size,
        (0, 0, 0, 0)
    )

    card_draw = ImageDraw.Draw(card)

    card_draw.rounded_rectangle(
        (42, 48, 1038, 650),
        radius=42,
        fill=(255, 255, 255, 150),
        outline=(255, 255, 255, 220),
        width=4
    )

    image = Image.alpha_composite(
        image,
        card
    )

    draw = ImageDraw.Draw(image)

    text_fill = (
        224,
        32,
        32,
        255
    )

    white_stroke = (
        255,
        255,
        255,
        255
    )

    # --------------------------------------------
    # TITLE
    # --------------------------------------------

    draw.text(
        (540, 115),
        "నేటి బైబిల్ వాక్యం",
        font=title_font,
        fill=text_fill,
        stroke_width=9,
        stroke_fill=white_stroke,
        anchor="mm"
    )

    # --------------------------------------------
    # VERSE
    # --------------------------------------------

    lines = wrap_text(
        draw,
        text,
        verse_font,
        860
    )

    # Maximum 6 lines
    lines = lines[:6]

    line_height = 78

    start_y = (
        330 -
        (len(lines) - 1)
        * line_height / 2
    )

    for index, line in enumerate(lines):

        draw.text(
            (
                540,
                start_y +
                index * line_height
            ),
            line,
            font=verse_font,
            fill=text_fill,
            stroke_width=8,
            stroke_fill=white_stroke,
            anchor="mm"
        )

    # --------------------------------------------
    # REFERENCE
    # --------------------------------------------

    draw.text(
        (540, 585),
        reference,
        font=reference_font,
        fill=text_fill,
        stroke_width=8,
        stroke_fill=white_stroke,
        anchor="mm"
    )

    # --------------------------------------------
    # FOOTER
    # --------------------------------------------

    draw.text(
        (540, 1290),
        "Telugu Christians world",
        font=footer_font,
        fill=(255, 255, 255, 255),
        stroke_width=3,
        stroke_fill=(105, 75, 45, 180),
        anchor="mm"
    )

    image.convert("RGB").save(
        output,
        "PNG",
        optimize=True
    )

    return output


# ============================================================
# TELEGRAM HELPERS
# ============================================================

def telegram_api(method):

    return (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/{method}"
    )


# ============================================================
# POST QUOTE
# ============================================================

def post_quote(data):

    image_path = make_quote_image(
        data["text"],
        data["reference"],
        data["reflection"]
    )

    # Escape generated content for Telegram HTML.
    quote = html.escape(
        str(data["text"])
    )

    reference = html.escape(
        str(data["reference"])
    )

    reflection = html.escape(
        str(data["reflection"])
    )

    caption = (
        "<b>📖 నేటి బైబిల్ వాక్యం</b>\n\n"
        f"\"{quote}\"\n\n"
        f"📍 <b>{reference}</b>\n\n"
        f"💭 {reflection}"
    )

    with open(
        image_path,
        "rb"
    ) as image_file:

        response = requests.post(
            telegram_api("sendPhoto"),

            files={
                "photo": image_file
            },

            data={
                "chat_id": CHANNEL_ID,
                "caption": caption,
                "parse_mode": "HTML"
            },

            timeout=30
        )

    if not response.ok:

        raise RuntimeError(
            "Telegram sendPhoto failed: "
            f"HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result}"
        )

    return result


# ============================================================
# QUIZ GENERATION
# ============================================================

def generate_quiz(history):

    previous = [
        x.get("question", "")
        for x in history
        if x.get("type") == "quiz"
        and x.get("question")
    ][-30:]

    prompt = f"""
"Telugu Christians world" కోసం ఒక తెలుగు Bible quiz తయారు చేయండి.

నియమాలు:

1. నిజమైన Bible information మాత్రమే ఉపయోగించండి.
2. పాత ప్రశ్నలను పునరావృతం చేయవద్దు.
3. కనీసం 4 options ఉండాలి.
4. exactly 4 options ఇవ్వండి.
5. answer_index తప్పనిసరిగా 0, 1, 2 లేదా 3 ఉండాలి.
6. explanation చిన్నగా మరియు స్పష్టంగా ఉండాలి.
7. reference సరైన Bible reference అయి ఉండాలి.
8. JSON మాత్రమే ఇవ్వండి.

ఇటీవల ఉపయోగించిన ప్రశ్నలు:

{json.dumps(previous, ensure_ascii=False)}

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
    "explanation": "సరైన సమాధానానికి చిన్న వివరణ",
    "reference": "గ్రంథం అధ్యాయం:వచనం"
}}
"""

    data = gemini(prompt)

    if not isinstance(data, dict):
        raise RuntimeError(
            "Invalid quiz response."
        )

    question = str(
        data.get("question", "")
    ).strip()

    options = data.get("options")

    answer_index = data.get(
        "answer_index"
    )

    explanation = str(
        data.get("explanation", "")
    ).strip()

    reference = str(
        data.get("reference", "")
    ).strip()

    if not question:
        raise RuntimeError(
            "Quiz question is empty."
        )

    if (
        not isinstance(options, list)
        or len(options) != 4
    ):
        raise RuntimeError(
            "Quiz must contain exactly 4 options."
        )

    options = [
        str(x).strip()
        for x in options
    ]

    if any(not x for x in options):
        raise RuntimeError(
            "Quiz contains empty options."
        )

    try:
        answer_index = int(
            answer_index
        )
    except (TypeError, ValueError):
        raise RuntimeError(
            "Invalid quiz answer_index."
        )

    if answer_index not in range(4):
        raise RuntimeError(
            "answer_index must be 0-3."
        )

    return {
        "question": question,
        "options": options,
        "answer_index": answer_index,
        "explanation": explanation,
        "reference": reference
    }


# ============================================================
# POST QUIZ
# ============================================================

def post_quiz(data):

    response = requests.post(
        telegram_api("sendPoll"),

        json={
            "chat_id": CHANNEL_ID,
            "question": data["question"],
            "options": data["options"],
            "type": "quiz",
            "correct_option_id": data["answer_index"],
            "is_anonymous": True,
            "explanation": data.get(
                "explanation",
                ""
            )[:200]
        },

        timeout=30
    )

    if not response.ok:

        raise RuntimeError(
            "Telegram sendPoll failed: "
            f"HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    result = response.json()

    if not result.get("ok"):

        raise RuntimeError(
            f"Telegram poll API error: {result}"
        )

    return result


# ============================================================
# KNOWLEDGE GENERATION
# ============================================================

def generate_knowledge(history):

    previous = [
        x.get("title", "")
        for x in history
        if x.get("type") == "knowledge"
        and x.get("title")
    ][-20:]

    prompt = f"""
"Telugu Christians world" కోసం ఉపయోగకరమైన తెలుగు
Bible knowledge post తయారు చేయండి.

నియమాలు:

1. నిజమైన Bible information మాత్రమే ఉపయోగించండి.
2. పాత topics పునరావృతం చేయవద్దు.
3. కనీసం 3 ముఖ్యమైన points ఇవ్వండి.
4. సహజమైన తెలుగు ఉపయోగించండి.
5. JSON మాత్రమే ఇవ్వండి.

ఇటీవల ఉపయోగించిన topics:

{json.dumps(previous, ensure_ascii=False)}

JSON:

{{
    "title": "శీర్షిక",
    "content": "కనీసం 3 ముఖ్యమైన points",
    "reference": "సంబంధిత Bible reference"
}}
"""

    data = gemini(prompt)

    if not isinstance(data, dict):
        raise RuntimeError(
            "Invalid knowledge response."
        )

    title = str(
        data.get("title", "")
    ).strip()

    content = str(
        data.get("content", "")
    ).strip()

    reference = str(
        data.get("reference", "")
    ).strip()

    if not title:
        raise RuntimeError(
            "Knowledge title is empty."
        )

    if not content:
        raise RuntimeError(
            "Knowledge content is empty."
        )

    return {
        "title": title,
        "content": content,
        "reference": reference
    }


# ============================================================
# POST KNOWLEDGE
# ============================================================

def post_knowledge(data):

    title = html.escape(
        str(data["title"])
    )

    content = html.escape(
        str(data["content"])
    )

    reference = html.escape(
        str(data["reference"])
    )

    message = (
        "<b>💡 నేటి బైబిల్ జ్ఞానం</b>\n\n"
        f"<b>{title}</b>\n\n"
        f"{content}\n\n"
        f"📍 {reference}"
    )

    response = requests.post(
        telegram_api("sendMessage"),

        json={
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "HTML"
        },

        timeout=30
    )

    if not response.ok:

        raise RuntimeError(
            "Telegram sendMessage failed: "
            f"HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    result = response.json()

    if not result.get("ok"):

        raise RuntimeError(
            f"Telegram message API error: {result}"
        )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    history = load_history()

    post_type = os.environ.get(
        "POST_TYPE",
        "quote"
    ).strip().lower()

    print(
        f"🚀 Starting post type: {post_type}"
    )

    try:

        # ----------------------------------------
        # QUOTE
        # ----------------------------------------

        if post_type == "quote":

            data = generate_quote(
                history
            )

            print(
                f"Generated quote: "
                f"{data['reference']}"
            )

            post_quote(data)

            history.append({
                "type": "quote",
                "text": data.get("text"),
                "reference": data.get(
                    "reference"
                ),
                "reflection": data.get(
                    "reflection"
                ),
                "timestamp":
                    datetime.now(
                        timezone.utc
                    ).isoformat()
            })

        # ----------------------------------------
        # QUIZ
        # ----------------------------------------

        elif post_type == "quiz":

            data = generate_quiz(
                history
            )

            print(
                f"Generated quiz: "
                f"{data['question']}"
            )

            post_quiz(data)

            history.append({
                "type": "quiz",
                "question":
                    data.get("question"),
                "options":
                    data.get("options"),
                "answer_index":
                    data.get("answer_index"),
                "explanation":
                    data.get("explanation"),
                "reference":
                    data.get("reference"),
                "timestamp":
                    datetime.now(
                        timezone.utc
                    ).isoformat()
            })

        # ----------------------------------------
        # KNOWLEDGE
        # ----------------------------------------

        elif post_type == "knowledge":

            data = generate_knowledge(
                history
            )

            print(
                f"Generated knowledge: "
                f"{data['title']}"
            )

            post_knowledge(data)

            history.append({
                "type": "knowledge",
                "title":
                    data.get("title"),
                "content":
                    data.get("content"),
                "reference":
                    data.get("reference"),
                "timestamp":
                    datetime.now(
                        timezone.utc
                    ).isoformat()
            })

        # ----------------------------------------
        # INVALID TYPE
        # ----------------------------------------

        else:

            raise ValueError(
                f"Unknown POST_TYPE: "
                f"{post_type}. "
                f"Use quote, quiz or knowledge."
            )

        save_history(history)

        print(
            f"✅ SUCCESS: {post_type} posted!"
        )

    except Exception as error:

        print(
            f"❌ ERROR: {error}"
        )

        sys.exit(1)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
