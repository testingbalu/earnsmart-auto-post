name: EarnSmart India Daily Post

on:
  workflow_dispatch:

  schedule:
    - cron: "30 3 * * *"

jobs:
  post-to-telegram:
    runs-on: ubuntu-latest

    steps:
      - name: Generate and publish daily post
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        run: |
          cat > telegram_post.py <<'PY'
          import os
          import sys
          import json
          import urllib.request
          import urllib.parse
          from datetime import datetime, timezone

          # ============================================================
          # CONFIGURATION
          # ============================================================

          BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
          CHAT_ID = "@LegitEarnIndia"

          if not BOT_TOKEN:
              print("ERROR: TELEGRAM_BOT_TOKEN secret is missing.")
              sys.exit(1)

          API_URL = "https://api.telegram.org/bot" + BOT_TOKEN

          # ============================================================
          # DAILY CONTENT
          # ============================================================

          topics = [
              {
                  "title": "Start Freelancing With One Skill",
                  "intro": "You do not need dozens of skills to start freelancing. Pick one useful service, practise it and build proof of your work.",
                  "image": "https://images.unsplash.com/photo-1553877522-43269d4ea984?auto=format&fit=crop&w=1200&q=85",
                  "details": [
                      "📋 JOB DESCRIPTION",
                      "Freelancers provide services to clients on a project or contract basis. Common services include writing, graphic design, video editing, web development, virtual assistance and data work.",
                      "",
                      "🛠️ SKILLS NEEDED",
                      "• One marketable skill",
                      "• Good communication",
                      "• Time management",
                      "• Basic proposal writing",
                      "• Ability to meet deadlines",
                      "",
                      "🚀 HOW TO START",
                      "1. Choose ONE service.",
                      "2. Practise it every day.",
                      "3. Create 3 sample projects.",
                      "4. Build a simple portfolio.",
                      "5. Apply only for jobs matching your skill.",
                      "",
                      "💼 LEGITIMATE JOB SOURCES",
                      "• Upwork",
                      "• Fiverr",
                      "• Freelancer",
                      "• PeoplePerHour",
                      "• LinkedIn Jobs",
                      "",
                      "💡 TIP",
                      "Do not pay someone to 'unlock' a guaranteed freelance job. Genuine clients normally pay for completed work rather than demanding a security deposit."
                  ],
                  "links": [
                      "https://www.upwork.com",
                      "https://www.fiverr.com",
                      "https://www.freelancer.com",
                      "https://www.peopleperhour.com"
                  ]
              },

              {
                  "title": "Learn WordPress Website Development",
                  "intro": "WordPress skills can lead to website-building, maintenance and freelance opportunities for businesses and individuals.",
                  "image": "https://images.unsplash.com/photo-1547658719-da2b51169166?auto=format&fit=crop&w=1200&q=85",
                  "details": [
                      "📋 JOB DESCRIPTION",
                      "WordPress developers create, customize and maintain websites. Work can include themes, plugins, landing pages, speed optimization, SEO and troubleshooting.",
                      "",
                      "🛠️ SKILLS NEEDED",
                      "• WordPress administration",
                      "• HTML and CSS basics",
                      "• Basic PHP knowledge",
                      "• Website hosting",
                      "• SEO fundamentals",
                      "• Plugin and theme management",
                      "",
                      "🚀 HOW TO START",
                      "1. Learn WordPress fundamentals.",
                      "2. Create 2–3 practice websites.",
                      "3. Learn one page builder.",
                      "4. Learn basic HTML/CSS.",
                      "5. Create a portfolio.",
                      "",
                      "💼 JOB SOURCES",
                      "• Upwork",
                      "• Fiverr",
                      "• PeoplePerHour",
                      "• Codeable",
                      "• LinkedIn Jobs",
                      "",
                      "💡 TIP",
                      "Start with small website fixes instead of trying to build complex websites immediately."
                  ],
                  "links": [
                      "https://wordpress.org/learn/",
                      "https://www.codeable.io",
                      "https://www.upwork.com",
                      "https://www.fiverr.com"
                  ]
              },

              {
                  "title": "Learn Video Editing",
                  "intro": "Video editing is useful for YouTube videos, Instagram Reels, Shorts, advertisements and business content.",
                  "image": "https://images.unsplash.com/photo-1574717024653-61fd2cf4d44d?auto=format&fit=crop&w=1200&q=85",
                  "details": [
                      "📋 JOB DESCRIPTION",
                      "Video editors turn raw footage into finished videos by cutting clips, improving audio, adding transitions, captions and visual effects.",
                      "",
                      "🛠️ SKILLS NEEDED",
                      "• Video editing software",
                      "• Storytelling",
                      "• Audio editing",
                      "• Captions and subtitles",
                      "• Basic color correction",
                      "• Short-form video editing",
                      "",
                      "🚀 HOW TO START",
                      "1. Learn CapCut, DaVinci Resolve or another editor.",
                      "2. Practise using free footage.",
                      "3. Create 5 sample videos.",
                      "4. Build a showreel.",
                      "5. Offer editing services to creators and small businesses.",
                      "",
                      "💼 JOB SOURCES",
                      "• Fiverr",
                      "• Upwork",
                      "• LinkedIn",
                      "• Local businesses",
                      "",
                      "💡 TIP",
                      "Short-form editing is a practical starting point because creators regularly need Reels and Shorts."
                  ],
                  "links": [
                      "https://www.blackmagicdesign.com/products/davinciresolve",
                      "https://www.fiverr.com",
                      "https://www.upwork.com"
                  ]
              },

              {
                  "title": "Learn Digital Marketing",
                  "intro": "Digital marketing covers SEO, social media, content, email and online advertising.",
                  "image": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=85",
                  "details": [
                      "📋 JOB DESCRIPTION",
                      "Digital marketers help businesses attract customers through search engines, social media, websites, content and advertising.",
                      "",
                      "🛠️ SKILLS NEEDED",
                      "• SEO basics",
                      "• Social media management",
                      "• Content writing",
                      "• Analytics",
                      "• Basic advertising",
                      "• Research",
                      "",
                      "🚀 HOW TO START",
                      "1. Learn SEO fundamentals.",
                      "2. Create a small website or social page.",
                      "3. Practise writing useful content.",
                      "4. Learn analytics.",
                      "5. Create a small portfolio.",
                      "",
                      "💼 JOB SOURCES",
                      "• LinkedIn Jobs",
                      "• Indeed",
                      "• Naukri",
                      "• Upwork",
                      "• Fiverr",
                      "",
                      "💡 TIP",
                      "Build your own small project first. Real results make your portfolio much stronger."
                  ],
                  "links": [
                      "https://learndigital.withgoogle.com/digitalgarage",
                      "https://analytics.google.com",
                      "https://www.linkedin.com/jobs",
                      "https://www.naukri.com"
                  ]
              },

              {
                  "title": "Learn Excel For Better Job Opportunities",
                  "intro": "Excel is useful in administration, finance, sales, operations, data entry and reporting jobs.",
                  "image": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1200&q=85",
                  "details": [
                      "📋 JOB DESCRIPTION",
                      "Excel is widely used for spreadsheets, reporting, data cleaning, calculations, dashboards and business analysis.",
                      "",
                      "🛠️ SKILLS NEEDED",
                      "• SUM and IF",
                      "• VLOOKUP/XLOOKUP",
                      "• SUMIF/COUNTIF",
                      "• Pivot tables",
                      "• Charts",
                      "• Data cleaning",
                      "",
                      "🚀 HOW TO START",
                      "1. Learn basic formulas.",
                      "2. Practise with sample datasets.",
                      "3. Learn pivot tables.",
                      "4. Create one business dashboard.",
                      "5. Add the project to your portfolio.",
                      "",
                      "💼 JOB SOURCES",
                      "• Naukri",
                      "• Indeed",
                      "• LinkedIn Jobs",
                      "• Upwork",
                      "• Fiverr",
                      "",
                      "💡 TIP",
                      "Do not advertise yourself only as a 'data entry worker'. Excel + reporting + data analysis can provide stronger opportunities."
                  ],
                  "links": [
                      "https://support.microsoft.com/excel",
                      "https://www.kaggle.com/datasets",
                      "https://www.linkedin.com/jobs",
                      "https://www.upwork.com"
                  ]
              },

              {
                  "title": "Build A Professional CV",
                  "intro": "A good CV should quickly show your skills, projects, experience and measurable achievements.",
                  "image": "https://images.unsplash.com/photo-1586281380349-632531db7ed4?auto=format&fit=crop&w=1200&q=85",
                  "details": [
                      "📋 WHAT TO INCLUDE",
                      "A professional CV should contain your contact information, relevant skills, education, experience and projects.",
                      "",
                      "🛠️ IMPORTANT SECTIONS",
                      "• Professional summary",
                      "• Technical skills",
                      "• Work experience",
                      "• Projects",
                      "• Education",
                      "• Certifications",
                      "",
                      "🚀 HOW TO IMPROVE IT",
                      "1. Keep the layout simple.",
                      "2. Tailor the CV for each job.",
                      "3. Use measurable achievements.",
                      "4. Remove irrelevant information.",
                      "5. Check spelling and formatting.",
                      "",
                      "💼 WHERE TO FIND JOBS",
                      "• LinkedIn Jobs",
                      "• Naukri",
                      "• Indeed",
                      "• Company career pages",
                      "",
                      "💡 TIP",
                      "Never pay a recruiter simply because they promise guaranteed employment."
                  ],
                  "links": [
                      "https://www.canva.com/resumes/templates/",
                      "https://www.linkedin.com/jobs",
                      "https://www.naukri.com",
                      "https://www.indeed.com"
                  ]
              },

              {
                  "title": "Use AI Tools To Increase Productivity",
                  "intro": "AI can help with writing, research, coding, brainstorming and repetitive tasks when used carefully.",
                  "image": "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=85",
                  "details": [
                      "📋 WHAT YOU CAN DO",
                      "AI tools can assist with drafting content, summarizing information, generating ideas, coding assistance and repetitive work.",
                      "",
                      "🛠️ SKILLS NEEDED",
                      "• Writing clear prompts",
                      "• Fact checking",
                      "• Critical thinking",
                      "• Basic digital skills",
                      "• Privacy awareness",
                      "",
                      "🚀 HOW TO START",
                      "1. Learn one AI tool properly.",
                      "2. Use it for a real project.",
                      "3. Verify important information.",
                      "4. Create reusable prompts.",
                      "5. Combine AI with a valuable human skill.",
                      "",
                      "💼 POSSIBLE SERVICES",
                      "• Content assistance",
                      "• Research assistance",
                      "• AI-assisted design",
                      "• Automation",
                      "• Coding assistance",
                      "",
                      "💡 TIP",
                      "Do not believe websites promising guaranteed daily income just because you use AI."
                  ],
                  "links": [
                      "https://chatgpt.com",
                      "https://gemini.google.com",
                      "https://www.coursera.org",
                      "https://www.upwork.com"
                  ]
              },

              {
                  "title": "Start Virtual Assistance",
                  "intro": "Virtual assistants help businesses with administration, research, scheduling, customer support and online tasks.",
                  "image": "https://images.unsplash.com/photo-1497215842964-222b430dc094?auto=format&fit=crop&w=1200&q=85",
                  "details": [
                      "📋 JOB DESCRIPTION",
                      "Virtual assistants provide remote administrative and operational support to businesses and individuals.",
                      "",
                      "🛠️ SKILLS NEEDED",
                      "• Email management",
                      "• Google Workspace",
                      "• Spreadsheet skills",
                      "• Communication",
                      "• Research",
                      "• Time management",
                      "",
                      "🚀 HOW TO START",
                      "1. Learn Google Docs and Sheets.",
                      "2. Practise email and calendar management.",
                      "3. Create sample administrative work.",
                      "4. Prepare a simple service profile.",
                      "5. Apply for beginner-friendly jobs.",
                      "",
                      "💼 JOB SOURCES",
                      "• Upwork",
                      "• Fiverr",
                      "• Freelancer",
                      "• PeoplePerHour",
                      "• LinkedIn",
                      "",
                      "💡 TIP",
                      "Never pay an unknown person for a 'registration fee' to receive a remote job."
                  ],
                  "links": [
                      "https://www.upwork.com",
                      "https://www.fiverr.com",
                      "https://www.freelancer.com",
                      "https://www.peopleperhour.com"
                  ]
              },

              {
                  "title": "Learn Basic Coding",
                  "intro": "Learning basic coding can open opportunities in websites, automation, software and technical freelancing.",
                  "image": "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?auto=format&fit=crop&w=1200&q=85",
                  "details": [
                      "📋 JOB DESCRIPTION",
                      "Coding is used to create websites, applications, automation scripts and software.",
                      "",
                      "🛠️ SKILLS NEEDED",
                      "• Python or JavaScript",
                      "• Logical thinking",
                      "• Problem solving",
                      "• Git basics",
                      "• Debugging",
                      "",
                      "🚀 HOW TO START",
                      "1. Choose one programming language.",
                      "2. Learn the fundamentals.",
                      "3. Build small projects.",
                      "4. Upload projects to GitHub.",
                      "5. Gradually learn advanced concepts.",
                      "",
                      "💼 OPPORTUNITIES",
                      "• Web development",
                      "• Automation",
                      "• WordPress development",
                      "• Freelancing",
                      "• Junior developer jobs",
                      "",
                      "💡 TIP",
                      "Do not try to learn five programming languages at once. Become useful with one first."
                  ],
                  "links": [
                      "https://www.freecodecamp.org",
                      "https://github.com",
                      "https://www.codecademy.com",
                      "https://www.upwork.com"
                  ]
              },

              {
                  "title": "Create And Sell Digital Products",
                  "intro": "Templates, spreadsheets, checklists, guides and other digital products can solve specific customer problems.",
                  "image": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1200&q=85",
                  "details": [
                      "📋 WHAT IS A DIGITAL PRODUCT?",
                      "A digital product is something customers can receive electronically, such as templates, spreadsheets, guides, graphics or educational material.",
                      "",
                      "🛠️ SKILLS NEEDED",
                      "• Problem identification",
                      "• Product creation",
                      "• Basic design",
                      "• Marketing",
                      "• Customer research",
                      "",
                      "🚀 HOW TO START",
                      "1. Find a specific problem.",
                      "2. Create a simple solution.",
                      "3. Test it with potential customers.",
                      "4. Improve the product.",
                      "5. Sell through a suitable platform.",
           
