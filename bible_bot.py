import os
import json
import re
import requests
import sys
import mimetypes
import base64
from datetime import datetime, timezone
from io import BytesIO

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageEnhance,
    ImageFilter
)


# =========================================================
# ENVIRONMENT
# =========================================================

def require_env(name):
    value = os.environ.get(name)

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value


GEMINI_API_KEY = require_env("GEMINI_API_KEY")
BOT_TOKEN = require_env("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = require_env("BIBLE_CHANNEL_ID")


HISTORY_FILE = "posting_history.json"


# =========================================================
# GEMINI TEXT MODELS
# =========================================================

GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.7-flash"
]


# Image-generation model.
# This is separate from the text model.
IMAGE_MODEL = "gemini-3.1-flash-image"


# =========================================================
# HISTORY
# =========================================================

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

    except Exception:
        pass

    return []


def save_history(history):

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


# =========================================================
# GEMINI TEXT GENERATION
# =========================================================

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
            "temperature": 0.8,
            "responseMimeType": "application/json"
        }
    }


    last_error = None


    for model in GEMINI_MODELS:

        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{model}:generateContent"
        )


        try:

            response = requests.post(

                url,

                headers={
                    "x-goog-api-key": GEMINI_API_KEY,
                    "Content-Type": "application/json"
                },

                json=payload,

                timeout=90
            )


            if response.ok:

                body = response.json()

                text = (
                    body["candidates"][0]
                    ["content"]["parts"][0]["text"]
                )


                text = text.strip()


                text = re.sub(
                    r"^```json\s*",
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


                return json.loads(text)


            last_error = (
                f"{model}: HTTP "
                f"{response.status_code}: "
                f"{response.text[:800]}"
            )


            if response.status_code == 404:
                continue


            break


        except Exception as error:

            last_error = str(error)


    raise RuntimeError(
        f"Gemini text API failed: {last_error}"
    )


# =========================================================
# GEMINI AI IMAGE GENERATION
# =========================================================

def generate_ai_background(
    quote_text,
    reference,
    reflection
):

    print("Generating AI Bible background...")


    prompt = f"""
Create a beautiful cinematic Christian Bible quote
background image.

Bible verse:
{quote_text}

Bible reference:
{reference}

Meaning/reflection:
{reflection}

IMPORTANT VISUAL REQUIREMENTS:

- Create a realistic, respectful Christian biblical scene.
- The visual must match the meaning of the Bible verse.
- Jesus may appear when appropriate to the meaning.
- If the verse is about protection, show Jesus protecting
  or comforting a person.
- If the verse is about fear, show Jesus bringing peace
  during a storm or difficult situation.
- If the verse is about strength, show Jesus beside a
  person who is struggling.
- If the verse is about hope, show Jesus with warm light,
  sunrise or a peaceful hopeful atmosphere.
- If the verse is about prayer, show a person praying
  with a peaceful Christian atmosphere.
- If the verse is about guidance, show Jesus walking with
  or guiding a person.
- If the verse is about forgiveness, show a compassionate
  and peaceful Christian scene.
- Use historically inspired biblical clothing and scenery.
- Jesus should look dignified, compassionate and natural.
- Use cinematic lighting.
- Use realistic high-quality Christian artwork.
- Create strong visual depth.
- Keep the central/upper-middle area relatively dark or
  visually simple because Telugu text will be placed there.
- Do NOT generate any text.
- Do NOT generate Bible verses.
- Do NOT generate letters.
- Do NOT generate logos.
- Do NOT generate watermarks.
- Do NOT generate modern advertisements.
- Do NOT put words inside the image.
- Square 1:1 composition.
- Suitable for a Telegram Bible quote card.
"""


    payload = {

        "model": IMAGE_MODEL,

        "input": prompt,

        "response_format": {
            "type": "image",
            "aspect_ratio": "1:1",
            "image_size": "1K"
        }
    }


    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/interactions"
    )


    response = requests.post(

        url,

        headers={
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json"
        },

        json=payload,

        timeout=180
    )


    if not response.ok:

        raise RuntimeError(
            "Gemini image generation failed: "
            f"HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )


    body = response.json()


    # Current API provides output_image.
    output_image = body.get("output_image")


    if output_image:

        data = output_image.get("data")

        if data:

            return Image.open(
                BytesIO(
                    base64.b64decode(data)
                )
            ).convert("RGB")


    # Fallback: inspect interaction steps.
    steps = body.get("steps", [])


    for step in steps:

        if step.get("type") != "model_output":
            continue


        content = step.get("content", [])


        for block in content:

            if block.get("type") == "image":

                data = block.get("data")


                if data:

                    return Image.open(
                        BytesIO(
                            base64.b64decode(data)
                        )
                    ).convert("RGB")


    raise RuntimeError(
        "Gemini returned no image data."
    )


# =========================================================
# FALLBACK BACKGROUND
# =========================================================

def create_fallback_background():

    width = 1080
    height = 1080


    image = Image.new(
        "RGB",
        (width, height)
    )


    draw = ImageDraw.Draw(image)


    for y in range(height):

        t = y / height

        r = int(15 + 55 * t)
        g = int(25 + 45 * t)
        b = int(45 + 35 * t)


        draw.line(
            (0, y, width, y),
            fill=(r, g, b)
        )


    # Simple mountains
    mountain1 = [
        (0, 800),
        (180, 700),
        (330, 780),
        (520, 620),
        (700, 760),
        (880, 650),
        (1080, 780),
        (1080, 1080),
        (0, 1080)
    ]


    draw.polygon(
        mountain1,
        fill=(18, 22, 28)
    )


    # Moon/light
    draw.ellipse(
        (760, 100, 900, 240),
        fill=(235, 220, 170)
    )


    return image


# =========================================================
# TELUGU FONT
# =========================================================

def find_telugu_font():

    fonts = [

        "/usr/share/fonts/truetype/noto/"
        "NotoSansTelugu-Regular.ttf",

        "/usr/share/fonts/truetype/noto/"
        "NotoSansTelugu-Medium.ttf",

        "/usr/share/fonts/opentype/noto/"
        "NotoSansTelugu-Regular.ttf"

    ]


    for font in fonts:

        if os.path.exists(font):
            return font


    try:

        for root, dirs, files in os.walk(
            "/usr/share/fonts"
        ):

            for filename in files:

                if (
                    "Telugu" in filename
                    or
                    "telugu" in filename
                ):

                    return os.path.join(
                        root,
                        filename
                    )

    except Exception:
        pass


    raise FileNotFoundError(
        "Telugu font not found."
    )


# =========================================================
# TEXT WRAPPING
# =========================================================

def wrap_text(
    draw,
    text,
    font,
    max_width
):

    words = text.split()

    lines = []

    current = ""


    for word in words:

        test = (
            f"{current} {word}"
        ).strip()


        box = draw.textbbox(
            (0, 0),
            test,
            font=font
        )


        width = box[2] - box[0]


        if width <= max_width:

            current = test

        else:

            if current:
                lines.append(current)

            current = word


    if current:
        lines.append(current)


    return lines


# =========================================================
# CREATE QUOTE IMAGE
# =========================================================

def make_quote_image(
    text,
    reference,
    reflection,
    output="quote_card.png"
):

    width = 1080
    height = 1080


    # -----------------------------------------------------
    # FIRST TRY AI-GENERATED BACKGROUND
    # -----------------------------------------------------

    try:

        background = generate_ai_background(
            text,
            reference,
            reflection
        )

        print(
            "SUCCESS: AI Bible background generated."
        )

    except Exception as error:

        print(
            "WARNING: AI image generation failed."
        )

        print(
            "Reason:",
            str(error)
        )

        print(
            "Using fallback background so post "
            "will not fail."
        )

        background = create_fallback_background()


    # -----------------------------------------------------
    # RESIZE / CROP
    # -----------------------------------------------------

    background = background.convert("RGB")


    bg_ratio = (
        background.width /
        background.height
    )


    target_ratio = 1.0


    if bg_ratio > target_ratio:

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


    background = background.crop(
        (
            left,
            top,
            left + new_width,
            top + new_height
        )
    )


    background = background.resize(
        (width, height),
        Image.Resampling.LANCZOS
    )


    # -----------------------------------------------------
    # DARKEN BACKGROUND
    # -----------------------------------------------------

    background = ImageEnhance.Brightness(
        background
    ).enhance(0.62)


    # Slight blur makes text cleaner.
    background = background.filter(
        ImageFilter.GaussianBlur(1.2)
    )


    image = background.convert("RGBA")


    # -----------------------------------------------------
    # DARK OVERLAY
    # -----------------------------------------------------

    overlay = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 0)
    )


    overlay_draw = ImageDraw.Draw(
        overlay
    )


    # Main readable area
    overlay_draw.rounded_rectangle(

        (45, 65, 1035, 765),

        radius=40,

        fill=(
            0,
            0,
            0,
            155
        ),

        outline=(
            235,
            190,
            80,
            230
        ),

        width=3
    )


    image = Image.alpha_composite(
        image,
        overlay
    )


    draw = ImageDraw.Draw(image)


    font_path = find_telugu_font()


    title_font = ImageFont.truetype(
        font_path,
        34
    )


    verse_font = ImageFont.truetype(
        font_path,
        48
    )


    reference_font = ImageFont.truetype(
        font_path,
        36
    )


    footer_font = ImageFont.truetype(
        font_path,
        30
    )


    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    draw.text(

        (540, 125),

        "నేటి బైబిల్ వాక్యం",

        font=title_font,

        fill=(
            245,
            195,
            75
        ),

        anchor="mm"
    )


    # -----------------------------------------------------
    # QUOTE
    # -----------------------------------------------------

    lines = wrap_text(

        draw,

        text,

        verse_font,

        850
    )


    # Maximum readable lines
    lines = lines[:7]


    line_height = 72


    total_height = (
        len(lines) *
        line_height
    )


    start_y = (
        380 -
        total_height / 2
    )


    for index, line in enumerate(lines):

        y = (
            start_y +
            index * line_height
        )


        # Shadow
        draw.text(

            (540 + 2, y + 2),

            line,

            font=verse_font,

            fill=(
                0,
                0,
                0
            ),

            anchor="mm"
        )


        draw.text(

            (540, y),

            line,

            font=verse_font,

            fill=(
                255,
                255,
                255
            ),

            anchor="mm"
        )


    # -----------------------------------------------------
    # REFERENCE
    # -----------------------------------------------------

    draw.text(

        (540, 670),

        reference,

        font=reference_font,

        fill=(
            245,
            195,
            75
        ),

        anchor="mm"
    )


    # -----------------------------------------------------
    # BOTTOM BRANDING
    # -----------------------------------------------------

    # Add a subtle dark bottom gradient.
    bottom_overlay = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 0)
    )


    bottom_draw = ImageDraw.Draw(
        bottom_overlay
    )


    bottom_draw.rectangle(

        (0, 900, width, height),

        fill=(
            0,
            0,
            0,
            120
        )
    )


    image = Image.alpha_composite(
        image,
        bottom_overlay
    )


    draw = ImageDraw.Draw(image)


    draw.text(

        (540, 990),

        "Telugu Christians world",

        font=footer_font,

        fill=(
            255,
            255,
            255
        ),

        anchor="mm"
    )


    image = image.convert("RGB")


    image.save(
        output,
        "PNG",
        optimize=True
    )


    print(
        f"Quote image saved: {output}"
    )


    return output


# =========================================================
# GENERATE BIBLE QUOTE
# =========================================================

def generate_quote(history):

    previous = [

        item.get(
            "text",
            ""
        )

        for item in history

        if item.get("type") in (
            "quote",
            "verse"
        )

    ][-30:]


    prompt = f"""

మీరు "Telugu Christians world"
అనే తెలుగు క్రైస్తవ టెలిగ్రామ్ ఛానల్ కోసం
నాణ్యమైన రోజువారీ బైబిల్ కంటెంట్ తయారు చేస్తున్నారు.

ఒక నిజమైన బైబిల్ వాక్యాన్ని ఎంచుకోండి.

ఇప్పటికే ఉపయోగించిన వాక్యాలు:

{json.dumps(
    previous,
    ensure_ascii=False
)}

పాత వాక్యాన్ని పునరావృతం చేయకండి.

JSON మాత్రమే ఇవ్వండి:

{{
  "text": "తెలుగులో సహజమైన మరియు అర్థవంతమైన బైబిల్ వాక్యం",
  "reference": "గ్రంథం అధ్యాయం:వచనం",
  "reflection": "ఈ వాక్యం మన జీవితానికి చెప్పే ఉపయోగకరమైన ఆలోచన"
}}

నిబంధనలు:

1. నిజమైన బైబిల్ వాక్యం మాత్రమే.
2. reference వాక్యానికి తప్పనిసరిగా సరిపోవాలి.
3. సహజమైన తెలుగు ఉపయోగించండి.
4. వాక్యం చాలా పొడవుగా ఉండకూడదు.
5. reflection ఉపయోగకరంగా ఉండాలి.
6. అదే వాక్యాన్ని మళ్లీ ఉపయోగించకండి.
7. కల్పిత Bible reference ఇవ్వకండి.
"""


    return gemini(prompt)


# =========================================================
# GENERATE BIBLE QUIZ
# =========================================================

def generate_quiz(history):

    previous = [

        item.get(
            "question",
            ""
        )

        for item in history

        if item.get("type") == "quiz"

    ][-30:]


    prompt = f"""

Telugu Christians world కోసం
ఒక మంచి తెలుగు Bible quiz తయారు చేయండి.

ఇప్పటికే ఉపయోగించిన ప్రశ్నలు:

{json.dumps(
    previous,
    ensure_ascii=False
)}

పాత ప్రశ్నలను పునరావృతం చేయకండి.

నిబంధనలు:

1. ప్రశ్న స్పష్టంగా ఉండాలి.
2. 4 options ఉండాలి.
3. ఒక్కటే సరైన సమాధానం ఉండాలి.
4. నిజమైన బైబిల్ సమాచారంపై ఆధారపడాలి.
5. options చిన్నగా ఉండాలి.
6. answer_index 0,1,2,3 లో ఒకటి కావాలి.
7. explanation ఉపయోగకరంగా ఉండాలి.
8. reference తప్పనిసరిగా ఇవ్వాలి.

JSON మాత్రమే:

{{
  "question": "తెలుగులో ప్రశ్న",
  "options": [
    "ఎంపిక 1",
    "ఎంపిక 2",
    "ఎంపిక 3",
    "ఎంపిక 4"
  ],
  "answer_index": 0,
  "explanation": "సరైన సమాధానం ఎందుకు సరైందో చిన్న వివరణ",
  "reference": "గ్రంథం అధ్యాయం:వచనం"
}}
"""


    return gemini(prompt)


# =========================================================
# GENERATE KNOWLEDGE
# =========================================================

def generate_knowledge(history):

    previous = [

        item.get(
            "title",
            ""
        )

        for item in history

        if item.get("type") == "knowledge"

    ][-20:]


    prompt = f"""

"Telugu Christians world"
కోసం ఒక ఉపయోగకరమైన తెలుగు Bible knowledge post
తయారు చేయండి.

ఇప్పటికే ఉపయోగించిన topics:

{json.dumps(
    previous,
    ensure_ascii=False
)}

పాత topic పునరావృతం చేయకండి.

JSON మాత్రమే:

{{
  "title": "ఆకర్షణీయమైన తెలుగు శీర్షిక",
  "content": "వివరమైన కానీ సులభంగా అర్థమయ్యే తెలుగు Bible సమాచారం",
  "reference": "సంబంధిత Bible reference"
}}

నిబంధనలు:

1. నిజమైన Bible information మాత్రమే.
2. తప్పు Bible facts ఇవ్వకండి.
3. కనీసం 3 ముఖ్యమైన points ఉండాలి.
4. తెలుగు సహజంగా ఉండాలి.
5. content ఉపయోగకరంగా ఉండాలి.
6. reference ఇవ్వాలి.
"""


    return gemini(prompt)


# =========================================================
# POST QUOTE
# =========================================================

def post_quote(data):

    image_path = make_quote_image(

        data["text"],

        data["reference"],

        data["reflection"]
    )


    caption = (

        "<b>📖 నేటి బైబిల్ వాక్యం</b>\n\n"

        f""{data['text']}"\n\n"

        f"📍 <b>{data['reference']}</b>\n\n"

        f"💭 {data['reflection']}"
    )


    url = (
        "https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendPhoto"
    )


    with open(image_path, "rb") as image_file:

        files = {
            "photo": image_file
        }

        data_payload = {
            "chat_id": CHANNEL_ID,
            "caption": caption,
            "parse_mode": "HTML"
        }

        response = requests.post(
            url,
            files=files,
            data=data_payload,
            timeout=30
        )


    if not response.ok:

        raise RuntimeError(
            f"Telegram sendPhoto failed: "
            f"HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )


    return response.json()


# =========================================================
# POST QUIZ
# =========================================================

def post_quiz(data):

    text = (

        "<b>📚 నేటి బైబిల్ కవిజ్</b>\n\n"

        f"<b>{data['question']}</b>\n\n"

    )

    for i, option in enumerate(data["options"]):
        text += f"{chr(65 + i)}. {option}\n"

    url = (
        "https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30
    )

    if not response.ok:

        raise RuntimeError(
            f"Telegram sendMessage failed: "
            f"HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return response.json()


# =========================================================
# POST KNOWLEDGE
# =========================================================

def post_knowledge(data):

    text = (

        "<b>💡 నేటి బైబిల్ జ్ఞానం</b>\n\n"

        f"<b>{data['title']}</b>\n\n"

        f"{data['content']}\n\n"

        f"<i>📖 {data['reference']}</i>"
    )

    url = (
        "https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30
    )

    if not response.ok:

        raise RuntimeError(
            f"Telegram sendMessage failed: "
            f"HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return response.json()


# =========================================================
# MAIN
# =========================================================

def main():

    history = load_history()

    post_type = os.environ.get(
        "POST_TYPE",
        "quote"
    ).lower()

    try:

        if post_type == "quote":

            data = generate_quote(history)

            post_quote(data)

            history.append({
                "type": "quote",
                "text": data.get("text"),
                "reference": data.get("reference"),
                "reflection": data.get("reflection"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        elif post_type == "quiz":

            data = generate_quiz(history)

            post_quiz(data)

            history.append({
                "type": "quiz",
                "question": data.get("question"),
                "options": data.get("options"),
                "answer_index": data.get("answer_index"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        elif post_type == "knowledge":

            data = generate_knowledge(history)

            post_knowledge(data)

            history.append({
                "type": "knowledge",
                "title": data.get("title"),
                "content": data.get("content"),
                "reference": data.get("reference"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        else:

            raise ValueError(
                f"Unknown POST_TYPE: {post_type}"
            )


        save_history(history)

        print(
            f"✅ SUCCESS: {post_type} posted!"
        )


    except Exception as error:

        print(
            f"❌ ERROR: {str(error)}"
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
