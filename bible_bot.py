import os
import json
import re
import requests
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["BIBLE_CHANNEL_ID"]

HISTORY_FILE = "posting_history.json"

# Try the model from your previous error first,
# then automatically try the newer model if necessary.
GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.7-flash"
]


# =========================================================
# HISTORY
# =========================================================

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(
            history[-100:],
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# GEMINI
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
                timeout=60
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
                f"{model}: HTTP {response.status_code} "
                f"{response.text[:500]}"
            )

            # If model is not found, try next model.
            if response.status_code == 404:
                continue

            break

        except Exception as e:
            last_error = str(e)

    raise RuntimeError(
        f"Gemini API failed: {last_error}"
    )


# =========================================================
# TELEGRAM
# =========================================================

def telegram(method, data):

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/{method}"
    )

    response = requests.post(
        url,
        data=data,
        timeout=60
    )

    try:
        body = response.json()
    except Exception:
        body = {
            "ok": False,
            "description": response.text
        }

    if not body.get("ok"):

        raise RuntimeError(
            f"Telegram API error: {body}"
        )

    return body["result"]


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

    raise FileNotFoundError(
        "Telugu font not found."
    )


# =========================================================
# CREATE BIBLE QUOTE IMAGE
# =========================================================

def make_quote_image(
    text,
    reference,
    output="quote_card.png"
):

    width = 1080
    height = 1080

    image = Image.new(
        "RGB",
        (width, height),
        (18, 28, 38)
    )

    draw = ImageDraw.Draw(image)

    # Background gradient
    for y in range(height):

        if y < 760:

            t = y / 760

            r = int(18 + 42 * t)
            g = int(28 + 55 * t)
            b = int(38 + 60 * t)

        else:

            t = (y - 760) / 320

            r = int(60 - 30 * t)
            g = int(45 - 20 * t)
            b = int(35 - 10 * t)

        draw.line(
            (0, y, width, y),
            fill=(r, g, b)
        )

    # Mountain
    mountain = [
        (0, 850),
        (180, 790),
        (330, 820),
        (520, 690),
        (690, 790),
        (850, 735),
        (1080, 820),
        (1080, 1080),
        (0, 1080)
    ]

    draw.polygon(
        mountain,
        fill=(20, 25, 29)
    )

    font_path = find_telugu_font()

    title_font = ImageFont.truetype(
        font_path,
        34
    )

    verse_font = ImageFont.truetype(
        font_path,
        52
    )

    reference_font = ImageFont.truetype(
        font_path,
        38
    )

    # Main card
    draw.rounded_rectangle(
        (65, 85, 1015, 720),
        radius=35,
        fill=(0, 0, 0),
        outline=(230, 190, 80),
        width=3
    )

    draw.text(
        (540, 145),
        "నేటి బైబిల్ వాక్యం",
        font=title_font,
        fill=(245, 190, 75),
        anchor="mm"
    )

    # Wrap Telugu text
    lines = []
    current = ""

    for word in text.split():

        test = (
            f"{current} {word}"
        ).strip()

        box = draw.textbbox(
            (0, 0),
            test,
            font=verse_font
        )

        if box[2] <= 850:
            current = test

        else:

            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    lines = lines[:7]

    y = 245

    for line in lines:

        draw.text(
            (540, y),
            line,
            font=verse_font,
            fill=(250, 250, 250),
            anchor="mm"
        )

        y += 70

    draw.text(
        (540, 650),
        reference,
        font=reference_font,
        fill=(245, 190, 75),
        anchor="mm"
    )

    draw.text(
        (540, 1010),
        "Telugu Christians world",
        font=title_font,
        fill=(245, 245, 245),
        anchor="mm"
    )

    image.save(
        output,
        "PNG"
    )

    return output


# =========================================================
# GENERATE BIBLE QUOTE
# =========================================================

def generate_quote(history):

    previous = [
        item.get("text", "")
        for item in history
        if item.get("type") == "quote"
    ][-20:]

    prompt = f"""
మీరు Telugu Christians world అనే తెలుగు క్రైస్తవ టెలిగ్రామ్
ఛానల్ కోసం నాణ్యమైన రోజువారీ బైబిల్ కంటెంట్ తయారు చేస్తున్నారు.

ఒక నిజమైన బైబిల్ వాక్యాన్ని ఎంచుకోండి.

ముందు ఉపయోగించిన వాక్యాలు:
{json.dumps(previous, ensure_ascii=False)}

వాక్యం పునరావృతం కాకూడదు.

JSON మాత్రమే ఇవ్వండి:

{{
  "text": "తెలుగులో చిన్నదైన, అర్థవంతమైన బైబిల్ వాక్యం",
  "reference": "గ్రంథం అధ్యాయం:వచనం",
  "reflection": "ఈ వాక్యం మన జీవితానికి చెప్పే చిన్న ఆలోచన"
}}

నిబంధనలు:

1. వాక్యం కల్పితం కాకూడదు.
2. గ్రంథ సూచన వాక్యానికి సరిపోవాలి.
3. సహజమైన తెలుగు ఉపయోగించండి.
4. reflection ఉపయోగకరంగా ఉండాలి.
5. చాలా చిన్న సమాచారం ఇవ్వకండి.
"""

    return gemini(prompt)


# =========================================================
# GENERATE BIBLE QUIZ
# =========================================================

def generate_quiz(history):

    previous = [
        item.get("question", "")
        for item in history
        if item.get("type") == "quiz"
    ][-30:]

    prompt = f"""
Telugu Christians world కోసం ఒక మంచి తెలుగు Bible quiz తయారు చేయండి.

ఇప్పటికే ఉపయోగించిన ప్రశ్నలు:

{json.dumps(previous, ensure_ascii=False)}

పాత ప్రశ్నలను పునరావృతం చేయకండి.

నిబంధనలు:

1. ప్రశ్న స్పష్టంగా ఉండాలి.
2. 4 options ఉండాలి.
3. ఒక్కటే సరైన సమాధానం ఉండాలి.
4. నిజమైన బైబిల్ సమాచారంపై ఆధారపడాలి.
5. options చిన్నగా ఉండాలి.
6. సరైన answer_index 0,1,2,3 లో ఒకటి కావాలి.
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
# POST QUOTE
# =========================================================

def post_quote(data):

    image_path = make_quote_image(
        data["text"],
        data["reference"]
    )

    caption = (
        "<b>📖 నేటి బైబిల్ వాక్యం</b>\n\n"
        f"“{data['text']}”\n\n"
        f"📍 <b>{data['reference']}</b>\n\n"
        f"💭 {data['reflection']}\n\n"
        "🙏 ఈ వాక్యాన్ని ఈరోజు గుర్తుంచుకోండి.\n\n"
        "🔔 @Christians_world"
    )

    with open(
        image_path,
        "rb"
    ) as photo:

        url = (
            f"https://api.telegram.org/"
            f"bot{BOT_TOKEN}/sendPhoto"
        )

        response = requests.post(
            url,
            data={
                "chat_id": CHANNEL_ID,
                "caption": caption,
                "parse_mode": "HTML"
            },
            files={
                "photo": photo
            },
            timeout=60
        )

    body = response.json()

    if not body.get("ok"):

        raise RuntimeError(
            f"Telegram sendPhoto failed: {body}"
        )


# =========================================================
# POST QUIZ
# =========================================================

def post_quiz(data):

    options = [
        str(option).strip()
        for option in data["options"]
    ]

    if len(options) != 4:
        raise ValueError(
            "Quiz must contain exactly 4 options."
        )

    answer_index = int(
        data["answer_index"]
    )

    if answer_index not in range(4):

        raise ValueError(
            "answer_index must be 0, 1, 2 or 3."
        )

    question = str(
        data["question"]
    ).strip()

    explanation = (
        f"{data['explanation']} "
        f"📖 {data['reference']}"
    )

    explanation = explanation[:200]

    telegram(
        "sendPoll",
        {
            "chat_id": CHANNEL_ID,
            "question": question,
            "options": json.dumps(
                options,
                ensure_ascii=False
            ),
            "type": "quiz",
            "is_anonymous": "true",
            "correct_option_ids": json.dumps(
                [answer_index]
            ),
            "explanation": explanation,
            "allows_multiple_answers": "false",
            "shuffle_options": "true"
        }
    )


# =========================================================
# MAIN
# =========================================================

def main():

    history = load_history()

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    post_type = os.environ.get(
        "POST_TYPE",
        "quiz"
    ).lower()

    print("===================================")
    print("TELUGU BIBLE TELEGRAM BOT")
    print("===================================")
    print(f"Post type: {post_type}")

    if post_type == "quote":

        data = generate_quote(
            history
        )

        post_quote(
            data
        )

        history.append(
            {
                "date": today,
                "type": "quote",
                "text": data["text"],
                "reference": data["reference"]
            }
        )

        print(
            "SUCCESS: Bible quote posted."
        )

    elif post_type == "quiz":

        data = generate_quiz(
            history
        )

        post_quiz(
            data
        )

        history.append(
            {
                "date": today,
                "type": "quiz",
                "question": data["question"]
            }
        )

        print(
            "SUCCESS: Bible quiz posted."
        )

    else:

        raise ValueError(
            "POST_TYPE must be quote or quiz."
        )

    save_history(
        history
    )

    print(
        "Posting history saved."
    )


if __name__ == "__main__":
    main()
