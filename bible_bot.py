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
    """Normalize whitespace/case so equivalent generated verses are rejected."""
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

    # Validate the model response locally as well as instructing the model.
    # This prevents a duplicate from ever reaching Telegram when Gemini ignores
    # the prompt or returns an equivalent verse with different whitespace/case.
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
    prompt = f"""Create a respectful cinematic Christian Bible quote background.
Verse: {quote}
Reference: {reference}
Meaning: {reflection}
Use a realistic biblical scene, square 1:1 composition, cinematic lighting, and
keep the central/upper-middle area dark and simple for Telugu text. Do not create
text, letters, logos, verses, or watermarks."""
    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
        json={"model": IMAGE_MODEL, "input": prompt, "response_format": {"type": "image", "aspect_ratio": "1:1", "image_size": "1K"}},
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
    image = Image.new("RGB", (1080, 1080))
    draw = ImageDraw.Draw(image)
    for y in range(1080):
        t = y / 1080
        draw.line((0, y, 1080, y), fill=(int(15 + 55 * t), int(25 + 45 * t), int(45 + 35 * t)))
    draw.polygon([(0, 800), (180, 700), (330, 780), (520, 620), (700, 760), (880, 650), (1080, 780), (1080, 1080), (0, 1080)], fill=(18, 22, 28))
    draw.ellipse((760, 100, 900, 240), fill=(235, 220, 170))
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
    side = min(background.size)
    left, top = (background.width - side) // 2, (background.height - side) // 2
    image = background.crop((left, top, left + side, top + side)).resize((1080, 1080), Image.Resampling.LANCZOS)
    image = ImageEnhance.Brightness(image).enhance(0.62).filter(ImageFilter.GaussianBlur(1.2)).convert("RGBA")
    overlay = Image.new("RGBA", image.size)
    ImageDraw.Draw(overlay).rounded_rectangle((45, 65, 1035, 765), radius=40, fill=(0, 0, 0, 155), outline=(235, 190, 80, 230), width=3)
    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)
    font = find_telugu_font()
    title, verse, ref, footer = (ImageFont.truetype(font, size) for size in (34, 48, 36, 30))
    draw.text((540, 125), "నేటి బైబిల్ వాక్యం", font=title, fill=(245, 195, 75), anchor="mm")
    lines = wrap_text(draw, text, verse, 850)[:7]
    start = 380 - len(lines) * 72 / 2
    for index, line in enumerate(lines):
        y = start + index * 72
        draw.text((542, y + 2), line, font=verse, fill=(0, 0, 0), anchor="mm")
        draw.text((540, y), line, font=verse, fill="white", anchor="mm")
    draw.text((540, 670), reference, font=ref, fill=(245, 195, 75), anchor="mm")
    bottom = Image.new("RGBA", image.size)
    ImageDraw.Draw(bottom).rectangle((0, 900, 1080, 1080), fill=(0, 0, 0, 120))
    image = Image.alpha_composite(image, bottom)
    ImageDraw.Draw(image).text((540, 990), "Telugu Christians world", font=footer, fill="white", anchor="mm")
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
