import os
import sys
import html
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Telegram channel username
CHAT_ID = "@LegitEarnIndia"

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ============================================================
# CHECK CONFIGURATION
# ============================================================

if not BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN secret is missing.")
    sys.exit(1)


# ============================================================
# TELEGRAM API
# ============================================================

def telegram_request(method, data=None):
    """
    Send a request to Telegram Bot API.
    """

    url = f"{API_URL}/{method}"

    if data is None:
        data = {}

    encoded = urllib.parse.urlencode(data).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=encoded,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            result = json.loads(raw)

    except Exception as e:
        print(f"Telegram request failed: {e}")
        raise

    if not result.get("ok"):
        print("Telegram API ERROR:")
        print(json.dumps(result, indent=2))
        raise RuntimeError(result)

    return result


# ============================================================
# TEST TELEGRAM CONNECTION
# ============================================================

print("Checking Telegram bot...")

me = telegram_request("getMe")

bot_username = me["result"].get("username", "unknown")

print(f"Bot connected successfully: @{bot_username}")


# ============================================================
# DAILY CONTENT
# ============================================================

topics = [

    {
        "title": "Start Freelancing With One Skill",

        "intro":
            "You don't need dozens of skills to start freelancing. "
            "Choose one useful skill, practise it and build proof of your work.",

        "image":
            "https://images.unsplash.com/photo-1553877522-43269d4ea984?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "Freelancing means providing a service to clients on a project or contract basis.",
            "Beginners can start with writing, graphic design, video editing, virtual assistance, WordPress, data work or programming.",
            "The important part is building real skills and a small portfolio instead of paying somebody for a guaranteed job."
        ],

        "skills": [
            "Writing or communication",
            "Basic computer skills",
            "Time management",
            "Client communication",
            "Proposal writing",
            "Meeting deadlines"
        ],

        "steps": [
            "Choose ONE skill.",
            "Practise it every day.",
            "Create 3 sample projects.",
            "Build a simple portfolio.",
            "Apply for small legitimate projects.",
            "Improve your profile using genuine client feedback."
        ],

        "jobs": [
            ("Upwork", "https://www.upwork.com"),
            ("Fiverr", "https://www.fiverr.com"),
            ("Freelancer", "https://www.freelancer.com"),
            ("PeoplePerHour", "https://www.peopleperhour.com")
        ],

        "warning":
            "Never pay someone who promises a guaranteed freelance job."
    },


    {
        "title": "Learn WordPress Website Development",

        "intro":
            "WordPress skills can be used to create websites, landing pages, "
            "business websites and freelance services.",

        "image":
            "https://images.unsplash.com/photo-1547658719-da2b51169166?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "WordPress developers create and maintain websites using the WordPress platform.",
            "Common work includes theme customization, plugin configuration, website maintenance, speed optimization and troubleshooting.",
            "Small businesses are often potential customers for simple websites."
        ],

        "skills": [
            "WordPress administration",
            "HTML and CSS basics",
            "Basic PHP knowledge",
            "SEO fundamentals",
            "Website security",
            "Hosting and domain basics"
        ],

        "steps": [
            "Install WordPress on a test website.",
            "Learn themes and plugins.",
            "Build 2 or 3 demo websites.",
            "Learn basic SEO.",
            "Learn website backup and security.",
            "Create a portfolio."
        ],

        "jobs": [
            ("Upwork", "https://www.upwork.com"),
            ("Fiverr", "https://www.fiverr.com"),
            ("Codeable", "https://www.codeable.io"),
            ("LinkedIn Jobs", "https://www.linkedin.com/jobs")
        ],

        "warning":
            "Do not install pirated WordPress themes or plugins. "
            "They can contain malware."
    },


    {
        "title": "Learn Video Editing",

        "intro":
            "Video editing is useful for YouTube videos, Instagram Reels, "
            "Shorts, advertisements and business content.",

        "image":
            "https://images.unsplash.com/photo-1574717024653-61fd2cf4d44d?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "Video editors turn raw footage into finished videos.",
            "A beginner can start with short-form videos and gradually move into long-form YouTube, advertisements and professional projects."
        ],

        "skills": [
            "Video cutting",
            "Transitions",
            "Audio editing",
            "Captions",
            "Colour correction",
            "Basic motion graphics"
        ],

        "steps": [
            "Choose an editor such as DaVinci Resolve.",
            "Learn cutting and timeline editing.",
            "Practise with free footage.",
            "Create 3 sample videos.",
            "Create a showreel.",
            "Start applying for small projects."
        ],

        "jobs": [
            ("Fiverr", "https://www.fiverr.com"),
            ("Upwork", "https://www.upwork.com"),
            ("LinkedIn Jobs", "https://www.linkedin.com/jobs"),
            ("Motion Array", "https://motionarray.com")
        ],

        "warning":
            "Avoid clients who ask you to download suspicious executable files."
    },


    {
        "title": "Learn Digital Marketing",

        "intro":
            "Digital marketing includes SEO, content marketing, social media, "
            "email marketing and online advertising.",

        "image":
            "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "Digital marketers help businesses attract customers online.",
            "Beginners can practise by creating their own small website, social media page or content project."
        ],

        "skills": [
            "SEO",
            "Content writing",
            "Social media",
            "Analytics",
            "Keyword research",
            "Basic advertising"
        ],

        "steps": [
            "Learn SEO fundamentals.",
            "Create a small website or page.",
            "Publish useful content.",
            "Study analytics.",
            "Learn basic advertising.",
            "Create case studies for your portfolio."
        ],

        "jobs": [
            ("LinkedIn Jobs", "https://www.linkedin.com/jobs"),
            ("Indeed India", "https://in.indeed.com"),
            ("Naukri", "https://www.naukri.com"),
            ("Upwork", "https://www.upwork.com")
        ],

        "warning":
            "Do not believe anyone promising guaranteed income from digital marketing."
    },


    {
        "title": "Learn Excel for Better Job Opportunities",

        "intro":
            "Excel is useful in administration, finance, sales, operations, "
            "data entry and many office jobs.",

        "image":
            "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "Excel can be a valuable entry-level skill because many businesses use spreadsheets for reports, records and analysis.",
            "Learning formulas, PivotTables and data cleaning can make you more useful in office jobs."
        ],

        "skills": [
            "SUM and IF",
            "VLOOKUP/XLOOKUP",
            "PivotTables",
            "Charts",
            "Data cleaning",
            "Conditional formatting"
        ],

        "steps": [
            "Learn basic formulas.",
            "Practise with sample datasets.",
            "Learn sorting and filtering.",
            "Learn PivotTables.",
            "Create one business dashboard.",
            "Add the project to your CV."
        ],

        "jobs": [
            ("Naukri", "https://www.naukri.com"),
            ("Indeed India", "https://in.indeed.com"),
            ("LinkedIn Jobs", "https://www.linkedin.com/jobs"),
            ("Upwork", "https://www.upwork.com")
        ],

        "warning":
            "Be careful with fake data-entry jobs asking for registration fees."
    },


    {
        "title": "Start Virtual Assistance",

        "intro":
            "Virtual assistants help businesses remotely with administration, "
            "research, scheduling, customer support and other online tasks.",

        "image":
            "https://images.unsplash.com/photo-1497215842964-222b430dc094?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "Virtual assistance can be suitable for people with good communication and organizational skills.",
            "Work may include email management, scheduling, research, spreadsheet work and customer support."
        ],

        "skills": [
            "Communication",
            "Google Workspace",
            "Microsoft Office",
            "Research",
            "Email management",
            "Time management"
        ],

        "steps": [
            "Learn Google Docs and Sheets.",
            "Learn professional email writing.",
            "Practise spreadsheet tasks.",
            "Create sample administrative work.",
            "Build a simple portfolio.",
            "Apply for beginner projects."
        ],

        "jobs": [
            ("Upwork", "https://www.upwork.com"),
            ("Fiverr", "https://www.fiverr.com"),
            ("Freelancer", "https://www.freelancer.com"),
            ("LinkedIn Jobs", "https://www.linkedin.com/jobs")
        ],

        "warning":
            "Never pay an employer to receive a job."
    },


    {
        "title": "Learn Basic Coding",

        "intro":
            "Learning programming can create opportunities in websites, "
            "automation, software and technical freelancing.",

        "image":
            "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "Beginners can start with Python or JavaScript.",
            "You do not need to become an expert immediately. Build small projects and gradually increase difficulty."
        ],

        "skills": [
            "One programming language",
            "Problem solving",
            "Basic algorithms",
            "Git",
            "Debugging",
            "Reading documentation"
        ],

        "steps": [
            "Choose Python or JavaScript.",
            "Learn variables and functions.",
            "Build small projects.",
            "Learn Git and GitHub.",
            "Create a portfolio.",
            "Apply for suitable beginner projects."
        ],

        "jobs": [
            ("Upwork", "https://www.upwork.com"),
            ("Fiverr", "https://www.fiverr.com"),
            ("Toptal", "https://www.toptal.com"),
            ("LinkedIn Jobs", "https://www.linkedin.com/jobs")
        ],

        "warning":
            "Never download unknown software from a client just because they promise payment."
    },


    {
        "title": "Create Digital Products",

        "intro":
            "Templates, spreadsheets, checklists, guides and other digital products "
            "can solve specific problems for customers.",

        "image":
            "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "Digital products are downloadable products that can be created once and sold repeatedly.",
            "Examples include templates, planners, spreadsheets, design assets and educational resources."
        ],

        "skills": [
            "Product creation",
            "Design",
            "Copywriting",
            "Marketing",
            "Customer research",
            "Basic online selling"
        ],

        "steps": [
            "Find a specific problem.",
            "Create a simple solution.",
            "Test it with potential users.",
            "Improve the product.",
            "Create a sales page.",
            "Promote it through legitimate channels."
        ],

        "jobs": [
            ("Gumroad", "https://gumroad.com"),
            ("Etsy", "https://www.etsy.com"),
            ("Creative Market", "https://creativemarket.com"),
            ("Shopify", "https://www.shopify.com")
        ],

        "warning":
            "Do not sell copyrighted material that you do not own."
    },


    {
        "title": "Build a Better CV",

        "intro":
            "A good CV should quickly show your skills, projects, experience "
            "and achievements.",

        "image":
            "https://images.unsplash.com/photo-1586281380349-632531db7ed4?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "Your CV is often the first thing a recruiter sees.",
            "A simple, readable and job-specific CV is generally more useful than a heavily designed document."
        ],

        "skills": [
            "Clear writing",
            "Achievement-focused descriptions",
            "Basic ATS awareness",
            "Attention to detail",
            "Job-specific customization"
        ],

        "steps": [
            "Write a clear professional summary.",
            "List relevant skills.",
            "Add projects and measurable achievements.",
            "Remove unnecessary information.",
            "Tailor the CV to each job.",
            "Check spelling before submitting."
        ],

        "jobs": [
            ("LinkedIn Jobs", "https://www.linkedin.com/jobs"),
            ("Indeed India", "https://in.indeed.com"),
            ("Naukri", "https://www.naukri.com")
        ],

        "warning":
            "Never pay someone who guarantees employment after creating your CV."
    },


    {
        "title": "Avoid Online Job Scams",

        "intro":
            "Fake online jobs often promise easy money and then ask applicants "
            "for deposits, registration fees or sensitive information.",

        "image":
            "https://images.unsplash.com/photo-1563013544-824ae1b704d3?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "Legitimate employers generally do not require applicants to pay a deposit to receive a normal job.",
            "Scammers may use fake company names, fake interview letters or pressure tactics."
        ],

        "skills": [
            "Company verification",
            "Online safety",
            "Critical thinking",
            "Recognising scam patterns",
            "Safe payment practices"
        ],

        "steps": [
            "Verify the company website.",
            "Check whether the job exists on the official careers page.",
            "Never share OTPs or passwords.",
            "Never pay for a guaranteed job.",
            "Be careful with unrealistic salary promises.",
            "Report suspicious activity."
        ],

        "jobs": [
            ("National Career Service", "https://www.ncs.gov.in"),
            ("LinkedIn Jobs", "https://www.linkedin.com/jobs"),
            ("Indeed India", "https://in.indeed.com"),
            ("Naukri", "https://www.naukri.com")
        ],

        "warning":
            "RED FLAG: Job + upfront payment + guaranteed income = investigate carefully."
    },


    {
        "title": "Improve Your Online Job Search",

        "intro":
            "Applying randomly to hundreds of jobs is usually less effective "
            "than using a targeted job-search strategy.",

        "image":
            "https://images.unsplash.com/photo-1521791136064-7986c2920216?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "A focused job search means finding roles that match your actual skills and tailoring your application.",
            "Tracking applications can also prevent missed follow-ups."
        ],

        "skills": [
            "Research",
            "CV customization",
            "Interview preparation",
            "Networking",
            "Application tracking"
        ],

        "steps": [
            "Choose a target job role.",
            "Create a matching CV.",
            "Set job alerts.",
            "Apply to suitable vacancies.",
            "Track applications.",
            "Prepare for interviews."
        ],

        "jobs": [
            ("LinkedIn Jobs", "https://www.linkedin.com/jobs"),
            ("Indeed India", "https://in.indeed.com"),
            ("Naukri", "https://www.naukri.com"),
            ("National Career Service", "https://www.ncs.gov.in")
        ],

        "warning":
            "Avoid recruiters who refuse to provide a verifiable company identity."
    },


    {
        "title": "Use AI Tools Productively",

        "intro":
            "AI tools can help with writing, research, coding, brainstorming "
            "and repetitive tasks when used responsibly.",

        "image":
            "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=85",

        "description": [
            "AI is becoming a useful productivity skill across many industries.",
            "The valuable skill is not simply using AI, but knowing how to give clear instructions and verify the results."
        ],

        "skills": [
            "Prompt writing",
            "Fact checking",
            "Research",
            "Data privacy awareness",
            "Workflow automation",
            "Critical thinking"
        ],

        "steps": [
            "Learn the basics of generative AI.",
            "Practise writing clear prompts.",
            "Use AI for small tasks.",
            "Verify important information.",
            "Protect confidential information.",
            "Build useful AI-assisted projects."
        ],

        "jobs": [
            ("Upwork", "https://www.upwork.com"),
            ("Fiverr", "https://www.fiverr.com"),
            ("LinkedIn Jobs", "https://www.linkedin.com/jobs"),
            ("We Work Remotely", "https://weworkremotely.com")
        ],

        "warning":
            "Never upload passwords, private documents or confidential customer data into an AI tool."
    }

]


# ============================================================
# SELECT DAILY TOPIC
# ============================================================

# Rotate topics based on calendar day.
today = datetime.now(timezone.utc).date()

day_number = toda
