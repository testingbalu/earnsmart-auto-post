import os
import json
import re
import sys
import base64
from datetime import datetime, timezone
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter


def require_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


GEMINI_API_KEY = require_env("GEMINI_API_KEY")
BOT_TOKEN = require_env("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = require_env("BIBLE_CHANNEL_ID")
HISTORY_FILE = "posting_history.json"
GEMINI_MODELS = ["gemini-3.6-flash", "gemini-3.7-flash"]
IMAGE_MODEL = "gemini-3.1-flash-image"


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history[-100:], file, ensure_ascii=False, indent=2)


def gemini(prompt):
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.8, "responseMimeType": "application/json"},
    }
    last_error = None
    for model in GEMINI_MODELS:
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                json=payload,
                timeout=90,
            )
            if response.ok:
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = re.sub(r"^```json\s*|\s*```$", "", text, flags=re.IGNORECASE)
                return json.loads(text)
            last_error = f"{model}: HTTP {response.status_code}: {response.text[:800]}"
            if response.status_code != 404:
                break
        except Exception as error:
            last_error = str(error)
    raise RuntimeError(f"Gemini text API failed: {last_error}")


def normalize_quote(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def used_quotes(history):
    return {
        normalize_quote(item.get("text"))
        for item in history
        if item.get("type") in ("quote", "verse") and normalize_quote(item.get("text"))
    }


def generate_quote(history):
    previous = [
        item.get("text", "")
        for item in history
        if item.get("type") in ("quote", "verse") and item.get("text")
    ]
    rejected = used_quotes(history)
    for attempt in range(8):
        prompt = f"""
మీరు Telugu Christians world అనే తెలుగు క్రైస్తవ టెలిగ్రామ్ ఛానల్ కోసం
ఒక నిజమైన, కొత్త తెలుగు బైబిల్ వాక్యాన్ని తయారు చేయండి.

ఇప్పటికే ఉపయోగించిన వాక్యాలు:
{json.dumps(previous, ensure_ascii=False)}

పై జాబితాలోని వాక్యాలను లేదా వాటికి సమానమైన వాక్యాలను మళ్లీ ఎంచుకోకండి.
JSON మాత్రమే ఇవ్వండి:
{{
  "text": "తెలుగులో సహజమైన మరియు అర్థవంతమైన బైబిల్ వాక్యం",
  "reference": "గ్రంథం అధ్యాయం:వచనం",
  "reflection": "ఈ వాక్యం మన జీవితానికి చెప్పే ఉపయోగకరమైన ఆలోచన"
}}
నిజమైన బైబిల్ వాక్యం, సరైన reference, సహజమైన తెలుగు మాత్రమే ఉపయోగించండి.
"""
        data = gemini(prompt)
        text = str(data.get("text", "")).strip()
        key = normalize_quote(text)
        if text and key not in rejected:
            return data
        print(f"Duplicate or empty quote rejected (attempt {attempt + 1}).")
        if text:
            previous.append(text)
            rejected.add(key)
    raise RuntimeError("Could not generate a unique Bible quote after 8 attempts.")


def generate_ai_background(quote, reference, reflection):
    prompt = f"""
Create a beautiful, bright, warm Christian Bible illustration for a Telugu Bible
verse card. The image must visually tell the story and meaning of this exact
verse, not use a generic background.

Verse: {quote}
Reference: {reference}
Meaning: {reflection}

VISUAL DIRECTION:
- Choose the scene based on the verse meaning: comfort and protection for fear,
  peaceful light for hope, Jesus helping someone for strength, prayer for a
  prayer verse, a path or Jesus walking beside someone for guidance, forgiveness
  and reconciliation for forgiveness, healing for healing, and joyful family or
  child-friendly scenes for love and kindness.
- Use a bright, soft, uplifting devotional illustration like a Christian greeting
  card: blue sky, warm sunlight, soft clouds, greenery, flowers, and gentle pastel
  colors where appropriate.
- Jesus should look compassionate, dignified, natural, and historically inspired.
- Keep the lower or side subject area visually rich; leave the upper third
  relatively uncluttered and light so Telugu text can be added later.
- Use a vertical 4:5 or portrait-friendly composition suitable for a Telegram card.
- Do not use a black background, dark cinematic mood, heavy vignette, or horror mood.
- Do not generate any text, Telugu letters, English letters, Bible verses, logos,
  signatures, labels, or watermarks inside the image.
"""
    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
        json={
            "model": IMAGE_MODEL,
            "input": prompt,
            "response_format": {"type": "image", "aspect_ratio": "4:5", "image_size": "1K"},
        },
        timeout=180,
    )
    if not response.ok:
        raise RuntimeError(f"Gemini image generation failed: HTTP {response.status_code}")
    body = response.json()
    candidates = []
    if body.get("output_image"):
        candidates.append(body["output_image"])
    for step in body.get("steps", []):
        for block in step.get("content", []):
            if step.get("type") == "model_output" and block.get("type") == "image":
                candidates.append(block)
    for item in candidates:
        if item.get("data"):
            return Image.open(BytesIO(base64.b64decode(item["data"]))).convert("RGB")
    raise RuntimeError("Gemini returned no image data.")


def fallback_background():
    image = Image.new("RGB", (1080, 1350), (211, 239, 255))
    draw = ImageDraw.Draw(image)
    for y in range(1350):
        t = y / 1350
        draw.line((0, y, 1080, y), fill=(int(205 + 35 * t), int(235 + 12 * t), int(255 - 15 * t)))
    draw.ellipse((780, 80, 980, 280), fill=(255, 244, 170))
    draw.ellipse((30, 850, 1150, 1500), fill=(181, 224, 157))
    draw.ellipse((120, 1000, 650, 1500), fill=(151, 205, 130))
    return image


def find_telugu_font():
    for root, _, files in os.walk("/usr/share/fonts"):
        for name in files:
            if "telugu" in name.lower() and name.endswith((".ttf", ".otf")):
                return os.path.join(root, name)
    raise FileNotFoundError("Telugu font not found.")


def wrap_text(draw, text, font, max_width):
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def make_quote_image(text, reference, reflection, output="quote_card.png"):
    try:
        background = generate_ai_background(text, reference, reflection)
    except Exception as error:
        print(f"WARNING: AI image generation failed: {error}; using fallback.")
        background = fallback_background()

    background = background.convert("RGB")
    target_ratio = 4 / 5
    source_ratio = background.width / background.height
    if source_ratio > target_ratio:
        new_height = background.height
        new_width = int(new_height * target_ratio)
    else:
        new_width = background.width
        new_height = int(new_width / target_ratio)
    left = (background.width - new_width) // 2
    top = (background.height - new_height) // 2
    image = background.crop((left, top, left + new_width, top + new_height)).resize((1080, 1350), Image.Resampling.LANCZOS)

    # Preserve the bright devotional look from the reference image. Only apply
    # a very light enhancement; never darken the whole image with a black layer.
    image = ImageEnhance.Color(image).enhance(1.08)
    image = ImageEnhance.Brightness(image).enhance(1.04)
    image = image.filter(ImageFilter.GaussianBlur(0.25)).convert("RGBA")

    draw = ImageDraw.Draw(image)
    font_path = find_telugu_font()
    title_font = ImageFont.truetype(font_path, 42)
    verse_font = ImageFont.truetype(font_path, 50)
    reference_font = ImageFont.truetype(font_path, 38)
    footer_font = ImageFont.truetype(font_path, 28)

    # A translucent white card keeps the colorful scene visible while matching
    # the white-edged red lettering style of the supplied example.
    card = Image.new("RGBA", image.size, (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card)
    card_draw.rounded_rectangle((42, 48, 1038, 650), radius=42, fill=(255, 255, 255, 150), outline=(255, 255, 255, 220), width=4)
    image = Image.alpha_composite(image, card)
    draw = ImageDraw.Draw(image)

    text_fill = (224, 32, 32, 255)
    white_stroke = (255, 255, 255, 255)
    draw.text((540, 115), "నేటి బైబిల్ వాక్యం", font=title_font, fill=text_fill, stroke_width=9, stroke_fill=white_stroke, anchor="mm")

    lines = wrap_text(draw, text, verse_font, 860)[:6]
    line_height = 78
    start_y = 330 - (len(lines) - 1) * line_height / 2
    for index, line in enumerate(lines):
        draw.text((540, start_y + index * line_height), line, font=verse_font, fill=text_fill, stroke_width=8, stroke_fill=white_stroke, anchor="mm")

    draw.text((540, 585), reference, font=reference_font, fill=text_fill, stroke_width=8, stroke_fill=white_stroke, anchor="mm")
    draw.text((540, 1290), "Telugu Christians world", font=footer_font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(105, 75, 45, 180), anchor="mm")
    image.convert("RGB").save(output, "PNG", optimize=True)
    return output


def post_quote(data):
    image_path = make_quote_image(data["text"], data["reference"], data["reflection"])
    caption = f"<b>📖 నేటి బైబిల్ వాక్యం</b>\n\n\"{data['text']}\"\n\n📍 <b>{data['reference']}</b>\n\n💭 {data['reflection']}"
    with open(image_path, "rb") as image_file:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            files={"photo": image_file},
            data={"chat_id": CHANNEL_ID, "caption": caption, "parse_mode": "HTML"},
            timeout=30,
        )
    if not response.ok:
        raise RuntimeError(f"Telegram sendPhoto failed: HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


def generate_quiz(history):
    previous = [x.get("question", "") for x in history if x.get("type") == "quiz"][-30:]
    return gemini(f'''Telugu Christians world కోసం ఒక తెలుగు Bible quiz తయారు చేయండి. పాత ప్రశ్నలను పునరావృతం చేయకండి: {json.dumps(previous, ensure_ascii=False)}
JSON మాత్రమే: {{"question":"ప్రశ్న","options":["1","2","3","4"],"answer_index":0,"explanation":"వివరణ","reference":"గ్రంథం అధ్యాయం:వచనం"}}''')


def generate_knowledge(history):
    previous = [x.get("title", "") for x in history if x.get("type") == "knowledge"][-20:]
    return gemini(f'''Telugu Christians world కోసం ఉపయోగకరమైన తెలుగు Bible knowledge post తయారు చేయండి. పాత topics పునరావృతం చేయకండి: {json.dumps(previous, ensure_ascii=False)}
JSON మాత్రమే: {{"title":"శీర్షిక","content":"కనీసం 3 ముఖ్యమైన points","reference":"సంబంధిత Bible reference"}}''')


def post_quiz(data):
    response = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll", json={"chat_id": CHANNEL_ID, "question": data["question"], "options": data["options"], "type": "quiz", "correct_option_id": data["answer_index"], "explanation": data["explanation"], "explanation_parse_mode": "HTML", "is_anonymous": True}, timeout=30)
    if not response.ok:
        raise RuntimeError(f"Telegram sendPoll failed: HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


def post_knowledge(data):
    response = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHANNEL_ID, "text": f"<b>💡 నేటి బైబిల్ జ్ఞానం</b>\n\n<b>{data['title']}</b>\n\n{data['content']}\n\n<i>📖 {data['reference']}</i>", "parse_mode": "HTML"}, timeout=30)
    if not response.ok:
        raise RuntimeError(f"Telegram sendMessage failed: HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


def main():
    history = load_history()
    post_type = os.environ.get("POST_TYPE", "quote").lower()
    try:
        if post_type == "quote":
            data = generate_quote(history)
            post_quote(data)
            history.append({"type": "quote", "text": data.get("text"), "reference": data.get("reference"), "reflection": data.get("reflection"), "timestamp": datetime.now(timezone.utc).isoformat()})
        elif post_type == "quiz":
            data = generate_quiz(history)
            post_quiz(data)
            history.append({"type": "quiz", "question": data.get("question"), "options": data.get("options"), "answer_index": data.get("answer_index"), "timestamp": datetime.now(timezone.utc).isoformat()})
        elif post_type == "knowledge":
            data = generate_knowledge(history)
            post_knowledge(data)
            history.append({"type": "knowledge", "title": data.get("title"), "content": data.get("content"), "reference": data.get("reference"), "timestamp": datetime.now(timezone.utc).isoformat()})
        else:
            raise ValueError(f"Unknown POST_TYPE: {post_type}")
        save_history(history)
        print(f"✅ SUCCESS: {post_type} posted!")
    except Exception as error:
        print(f"❌ ERROR: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
