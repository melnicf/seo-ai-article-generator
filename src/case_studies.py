"""Scrape and cache Lemon.io case studies from the public page and detail pages."""

import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from src.config import CASE_STUDIES_CACHE as CASE_STUDIES_DIR

CASE_STUDIES_INDEX_URL = "https://lemon.io/case-studies/"
CACHE_FILE = CASE_STUDIES_DIR / "case_studies.json"

# All known case study detail page URLs
CASE_STUDY_URLS = [
    "https://lemon.io/case-studies/lemonio-meets-skyfi/",
    "https://lemon.io/case-studies/lemoneyeo-meets-tvscientific/",
    "https://lemon.io/case-studies/lemonyeo-meets-fathom/",
    "https://lemon.io/case-studies/lemonyeo-meets-peptalkr/",
    "https://lemon.io/case-studies/lemonio-meets-savr/",
    "https://lemon.io/case-studies/lemonyeo-meets-velvettech/",
    "https://lemon.io/case-studies/currents/",
    "https://lemon.io/case-studies/scrumbly/",
    "https://lemon.io/case-studies/lemonio-meets-myndy/",
    "https://lemon.io/case-studies/lemonio-meets-adherium/",
    "https://lemon.io/case-studies/lemonio-meets-little-spoon/",
    "https://lemon.io/case-studies/lemonio-meets-realestateapi/",
]


def _clean_text(text: str) -> str:
    """Clean scraped text: normalize whitespace, strip."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _extract_quotes(soup: BeautifulSoup) -> list[dict]:
    """Extract all blockquote-style quotes with attribution from page."""
    quotes = []
    # Look for blockquotes and quote-like elements
    for bq in soup.find_all("blockquote"):
        text = _clean_text(bq.get_text())
        if len(text) > 20:
            quotes.append({"text": text, "author": ""})

    # Also look for elements with quote styling
    for el in soup.select("[class*='quote'], [class*='testimonial']"):
        text = _clean_text(el.get_text())
        if len(text) > 20 and text not in [q["text"] for q in quotes]:
            quotes.append({"text": text, "author": ""})

    return quotes


NAVIGATION_NOISE = {
    "start hiring", "find jobs", "login", "for developers", "for companies",
    "rate calculator", "how we vet developers", "faq for companies",
    "case studies", "testimonials", "about us", "view all services",
    "home", "hire with confidence", "hire talent", "get started",
    "get a dev", "job description", "start hiring", "place request",
    "looking for other role?", "looking for other skill?",
    "read more about our screening", "hire a miraculous dev",
    "get supreme devs", "get impressive engineers",
    "get passionate qualified devs", "hire best-fit devs",
    "hire trusted talent",
}

# Known navigation link prefixes to filter out
NAV_PREFIXES = ("hire ", "looking for", "view all", "get started", "place ")


def _is_navigation_text(text: str) -> bool:
    """Check if text is likely a navigation item, not actual content."""
    lower = text.lower().strip()
    if lower in NAVIGATION_NOISE:
        return True
    if any(lower.startswith(p) for p in NAV_PREFIXES):
        return True
    return False


def _extract_technologies(soup: BeautifulSoup) -> list:
    """Extract technology names from case study page."""
    technologies = []

    # Strategy 1: Find element containing "technolog" and look at parent container
    for el in soup.find_all(string=re.compile(r"technolog", re.IGNORECASE)):
        parent = el.parent
        if parent is None:
            continue
        # Walk up to find a container
        container = parent.parent if parent.parent else parent
        # Look for short text items in that container and its siblings
        for sibling in container.find_all(["span", "li", "a", "p", "div"]):
            text = _clean_text(sibling.get_text())
            # Skip the label itself and navigation items
            if "technolog" in text.lower():
                continue
            if 2 < len(text) < 25 and not _is_navigation_text(text):
                if text not in technologies:
                    technologies.append(text)

    # Strategy 2: Look for specific tech badge containers
    for el in soup.select("[class*='tech'], [class*='stack'], [class*='badge']"):
        text = _clean_text(el.get_text())
        if 2 < len(text) < 25 and not _is_navigation_text(text):
            if text not in technologies:
                technologies.append(text)

    # Filter out likely person names (two capitalized words with no tech indicators)
    tech_indicators = {
        "js", "css", "html", "api", "sdk", "ui", "ux", "ai", "ml", "db",
        "sql", "net", "ios", "devops", "react", "node", "vue", "angular",
        "python", "java", "swift", "flutter", "typescript", "javascript",
        "docker", "aws", "gcp", "azure", "linux", "git", "ci", "cd",
        "front-end", "back-end", "full-stack", "data", "cloud", "mobile",
    }
    filtered = []
    for t in technologies:
        lower = t.lower()
        # If it's two words both capitalized and no tech indicator, likely a name
        words = t.split()
        if len(words) == 2 and all(w[0].isupper() for w in words):
            if not any(ind in lower for ind in tech_indicators):
                continue
        filtered.append(t)

    technologies = filtered

    # Deduplicate: if we have "Python React Native DevOps" AND individual items,
    # keep only the individual items
    combined = [t for t in technologies if " " in t and len(t.split()) >= 3]
    if combined:
        individual = [t for t in technologies if t not in combined]
        if individual:
            technologies = individual

    return technologies[:15]  # Cap at 15 to prevent noise


def _extract_customer_quotes(soup: BeautifulSoup, full_text: str) -> list:
    """Extract customer quotes from case study page using multiple strategies."""
    quotes = []
    seen = set()

    def _add_quote(text):
        text = _clean_text(text)
        if len(text) > 30 and text not in seen and not _is_navigation_text(text):
            seen.add(text)
            quotes.append(text)

    # Strategy 1: Blockquotes
    for bq in soup.find_all("blockquote"):
        _add_quote(bq.get_text())

    # Strategy 2: Elements with quote/testimonial classes
    for el in soup.select(
        "[class*='quote'], [class*='testimonial'], [class*='review']"
    ):
        _add_quote(el.get_text())

    # Strategy 3: Italic or em text that's long enough to be a quote
    for el in soup.find_all(["em", "i"]):
        text = el.get_text()
        if len(text) > 40:
            _add_quote(text)

    # Strategy 4: Regex for text in curly/straight quotes in the full page text
    quote_patterns = [
        re.compile(r'\u201c(.{30,}?)\u201d', re.DOTALL),
        re.compile(r'\u2018(.{30,}?)\u2019', re.DOTALL),
        re.compile(r'"([^"]{30,}?)"'),
    ]
    for pattern in quote_patterns:
        for match in pattern.finditer(full_text):
            _add_quote(match.group(1))

    return quotes


def _scrape_detail_page(url: str):
    """Scrape a single case study detail page for rich content."""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  Warning: Could not fetch {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove nav, header, footer to reduce noise
    for tag in soup.find_all(["nav", "header", "footer"]):
        tag.decompose()

    full_text = soup.get_text(separator="\n", strip=True)

    # Extract H1 title
    h1 = soup.find("h1")
    title = _clean_text(h1.get_text()) if h1 else ""

    # Extract all H2 section headings
    h2_headings = [_clean_text(h.get_text()) for h in soup.find_all("h2")]
    # Filter out navigation-like headings
    h2_headings = [h for h in h2_headings if not _is_navigation_text(h)]

    # Extract paragraph text for the main body (skip short/navigation paras)
    paragraphs = []
    for p in soup.find_all("p"):
        text = _clean_text(p.get_text())
        if len(text) > 40 and not _is_navigation_text(text):
            paragraphs.append(text)

    body_text = "\n\n".join(paragraphs)

    # Extract customer quotes
    customer_quotes = _extract_customer_quotes(soup, full_text)

    # Extract technologies
    technologies = _extract_technologies(soup)

    return {
        "url": url,
        "title": title,
        "h2_headings": h2_headings,
        "body_text": body_text,
        "customer_quotes": customer_quotes,
        "technologies": technologies,
        "full_text_length": len(full_text),
    }


def scrape_case_studies(force: bool = False) -> dict:
    """Scrape all case study data from Lemon.io.

    Combines:
    - Card-level data from the index page (industry, headline, stats)
    - Rich detail from each case study's own page (full story, quotes, tech)
    - Testimonials from the case studies index page

    Returns dict with keys: case_studies, testimonials
    """
    if CACHE_FILE.exists() and not force:
        return json.loads(CACHE_FILE.read_text())

    print("Scraping Lemon.io case studies (index + 12 detail pages)...")

    # ── Card-level data (hardcoded from index page for reliability) ──
    cards = [
        {
            "company": "SkyFi",
            "industry": "Aerospace",
            "headline": "Scaling seamlessly to get things done",
            "stats": [
                "5 developers hired and onboarded within 2 weeks",
                "8 months working with Lemon.io",
                "3 tech stacks used",
            ],
        },
        {
            "company": "tvScientific",
            "industry": "Telecommunications",
            "headline": "Stretching funding to scale rapidly",
            "stats": [
                "1 day for the first perfect-match developer",
                "7 devs hired (more to come)",
                "13 months working together",
            ],
        },
        {
            "company": "Fathom",
            "industry": "Software",
            "headline": "Scaling their product with high-end talent",
            "stats": [
                "24 hours for perfect developer match",
                "6 SwiftUI developers hired",
                "18 months of successful partnership",
            ],
        },
        {
            "company": "Peptalkr",
            "industry": "Healthcare",
            "headline": "Streamlining their app for a full-scale launch",
            "stats": [
                "2 devs hired so far",
                "3 weeks for the first perfect developer hire",
                "4 months working together",
            ],
        },
        {
            "company": "SAVR",
            "industry": "Marketplace",
            "headline": "Building a planet-saving app with hand-picked devs",
            "stats": [
                "10 days between the intro call and the first line of code",
                "7 senior devs hired",
                "5 months working together",
            ],
        },
        {
            "company": "Velvet",
            "industry": "Event Planning",
            "headline": "Launching B2B app for NYC-based startup",
            "stats": [
                "7 months working together",
                "1 senior developer",
                "100% expectations achieved",
            ],
        },
        {
            "company": "Currents",
            "industry": "Software",
            "headline": "Scaling SaaS platform with skilled developers",
            "stats": [
                "4 developers hired",
                "7+ tech stacks used",
                "17 months working with Lemon.io",
            ],
        },
        {
            "company": "Scrumbly",
            "industry": "Marketplace / Local Hospitality",
            "headline": "Empowering a non-tech founder with app creation",
            "stats": [
                "1 trusted full-stack dev",
                "4+ tech stacks used",
                "17 months working with Lemon.io",
            ],
        },
        {
            "company": "MYNDY",
            "industry": "Mental Fitness",
            "headline": "Helping a non-technical founder build MYNDY to life",
            "stats": [
                "1 developer hired",
                "1 week to hire",
                "12 months of collaboration",
            ],
        },
        {
            "company": "Adherium",
            "industry": "Healthcare",
            "headline": "Helping to scale fast in the US market",
            "stats": [
                "4 engineers hired",
                "1 week to hire first dev",
                "Full rebuild of healthcare platform",
            ],
        },
        {
            "company": "Little Spoon",
            "industry": "Health & Nutrition / D2C",
            "headline": "100% engineering hire rate with Lemon",
            "stats": [
                "4 engineers hired",
                "3 years of partnership",
                "100% satisfaction rate",
            ],
        },
        {
            "company": "RealEstateAPI",
            "industry": "Real Estate / PropTech",
            "headline": "Helping to scale business without burning out its CTO",
            "stats": [
                "1 engineer hired",
                "1 week to start",
                "12 months of collaboration",
            ],
        },
    ]

    # ── Scrape each detail page for rich content ──
    studies = []
    for i, url in enumerate(CASE_STUDY_URLS):
        print(f"  [{i+1}/{len(CASE_STUDY_URLS)}] Scraping {url}")
        detail = _scrape_detail_page(url)

        card = cards[i] if i < len(cards) else {}
        entry = {**card}

        if detail:
            entry["url"] = detail["url"]
            entry["title"] = detail["title"]
            entry["body_text"] = detail["body_text"]
            entry["customer_quotes"] = detail["customer_quotes"]
            entry["technologies"] = detail["technologies"]
            entry["h2_headings"] = detail["h2_headings"]
        else:
            entry["url"] = url
            entry["title"] = card.get("headline", "")
            entry["body_text"] = ""
            entry["customer_quotes"] = []
            entry["technologies"] = []
            entry["h2_headings"] = []

        studies.append(entry)

    # ── Testimonials (from index page + case study pages) ──
    testimonials = [
        {
            "quote": "The experience with Lemon.io has been fantastic. The interview process has been good, the caliber of people – excellent and integration has been very smooth.",
            "author": "Marc Horowitz, COO of SkyFi",
            "industry": "Aerospace",
        },
        {
            "quote": "We needed extra developers to clean off all these bugs so the company could skyrocket.",
            "author": "Conor Macken, tvScientific",
            "industry": "Telecommunications",
        },
        {
            "quote": "The developers helped us speed up. They quickly learned their part of the app — and we're grateful for their contribution.",
            "author": "Conor Macken, tvScientific",
            "industry": "Telecommunications",
        },
        {
            "quote": "We really wanted to work with high-end talent, the candidates who hold their own. The candidates we were receiving from Lemon.io straight away were high quality.",
            "author": "Kenneth Miller, Founder of Fathom",
            "industry": "Software / AI",
        },
        {
            "quote": "If you were to hire an engineer from Lemon.io or an engineer from the States, would there be any difference in speed? There was really none. And that was the most impressive thing.",
            "author": "Kenneth Miller, Founder of Fathom",
            "industry": "Software / AI",
        },
        {
            "quote": "Our back-end lead is impressed with the level of knowledge both Lemon.io engineers demonstrate.",
            "author": "Monique Clark, Peptalkr Founder",
            "industry": "Healthcare",
        },
        {
            "quote": "The backend part of the project is now more straightforward and demands less API resources. At the same time, user experience and front-end are also refined and more intuitive.",
            "author": "Monique Clark, Peptalkr Founder",
            "industry": "Healthcare",
        },
        {
            "quote": "The level of Lemon.io developers' work has been consistently and considerably higher. Cost-wise, the marketplace is very competitive. It is a perfect mix of high value and high quality.",
            "author": "Cormac Jonas, SAVR Founder",
            "industry": "Marketplace / E-commerce",
        },
        {
            "quote": "We know that we can call Malky with any kind of crazy request — and generally, in 24 hours, we have at least a partial solution in place. That's amazing.",
            "author": "Cormac Jonas, SAVR Founder",
            "industry": "Marketplace / E-commerce",
        },
        {
            "quote": "Lemon saved me time by making sure that before I even took that first phone call, I had a list of candidates that were truly good potential matches.",
            "author": "Jaldeep Acharya, CTO of Velvet",
            "industry": "Event Planning / SaaS",
        },
        {
            "quote": "From day one, Maksym hasn't really behaved as a contractor. He's taken ownership over the work that he has been given and done it with the same enthusiasm and energy as a full-time employee.",
            "author": "Jaldeep Acharya, CTO of Velvet",
            "industry": "Event Planning / SaaS",
        },
        {
            "quote": "We were approximately a month and a half out from our launch date with our first customer, and we just needed an extra pair of hands to get us across the finish line on time.",
            "author": "Jaldeep Acharya, CTO of Velvet",
            "industry": "Event Planning / SaaS",
        },
        {
            "quote": "Lemon devs implemented core functionality for our products like advanced analytics features, complex distributed systems, optimizations, maintaining infrastructure, documentation, refactorings – basically every aspect of engineering and product activities.",
            "author": "Andrew Goldis, CEO of Currents",
            "industry": "Software / DevTools",
        },
        {
            "quote": "As soon as you have enough money – if you got funding right away, or if you are bootstrapped and you have enough revenue – that's the right point to start hiring because it's a huge booster to the business.",
            "author": "Andrew Goldis, CEO of Currents",
            "industry": "Software / DevTools",
        },
        {
            "quote": "We need people who are independent, who take responsibility for their activities. People who need less ramp up and can jump in right away.",
            "author": "Andrew Goldis, CEO of Currents",
            "industry": "Software / DevTools",
        },
        {
            "quote": "The main thing was I wanted someone that I could trust because I have no developing experience. With my Lemon developer, I very quickly realized he was someone that I could have a lot of confidence in.",
            "author": "Jackson Feldman, CEO of Scrumbly",
            "industry": "Marketplace / Local Hospitality",
        },
        {
            "quote": "He saw the vision right off the bat and he was super excited about it, really wanted to get working on it. He's been super upfront with me and really good with communicating.",
            "author": "Jackson Feldman, CEO of Scrumbly",
            "industry": "Marketplace / Local Hospitality",
        },
        {
            "quote": "It's become just as much of his project as my project, which is really cool.",
            "author": "Jackson Feldman, CEO of Scrumbly",
            "industry": "Marketplace / Local Hospitality",
        },
        {
            "quote": "Iryna, my point of contact, was super professional and super focused. It made me feel like she would find the person I needed, no matter what. I felt cared for.",
            "author": "Lissy Alden, MYNDY Founder",
            "industry": "Mental Fitness",
        },
        {
            "quote": "He owned the project from the start. I said upfront I wanted someone who wasn't afraid of conflict, and wouldn't be afraid to push back. Adriano has delivered on all fronts.",
            "author": "Lissy Alden, MYNDY Founder",
            "industry": "Mental Fitness",
        },
        {
            "quote": "Adriano is talented, a fast learner, and a great member of the team. He operates like he cares about MYNDY just as much as anyone else. He is so much a part of the team that I invited him to my wedding.",
            "author": "Lissy Alden, MYNDY Founder",
            "industry": "Mental Fitness",
        },
        {
            "quote": "They've shown up for me in a way no one else has. In a world where AI is supposed to be the answer to everything, Lemon made hiring feel human.",
            "author": "Lissy Alden, MYNDY Founder",
            "industry": "Mental Fitness",
        },
        {
            "quote": "I'm sitting here stunned, going, 'What is this? This is amazing.' With all four of the engineers, it's been like, 'I'm up and running and firing on all cylinders.'",
            "author": "David Haddad, Head of Product & Technology at Adherium",
            "industry": "Healthcare / MedTech",
        },
        {
            "quote": "It ended up being 50% cheaper. Lemon saved me from spending hours trying to source on my own or going through a lengthy, formal process with a recruiter. All the vetting happens upfront.",
            "author": "David Haddad, Head of Product & Technology at Adherium",
            "industry": "Healthcare / MedTech",
        },
        {
            "quote": "They just slot right in. There's regular communication across multiple time zones – they're part of the way we work now.",
            "author": "David Haddad, Head of Product & Technology at Adherium",
            "industry": "Healthcare / MedTech",
        },
        {
            "quote": "They're fantastic engineers who don't sit around twiddling their thumbs. They make stuff happen. They put the effort in, and that's what's made Lemon such a critical partner for us.",
            "author": "David Haddad, Head of Product & Technology at Adherium",
            "industry": "Healthcare / MedTech",
        },
        {
            "quote": "Whenever it becomes clear we need a new resource, I say, 'I got a guy,' and then immediately send the JD over to Lemon to see who they've got in mind. We get back potential candidates who are perfectly aligned with what we're looking for, every time.",
            "author": "Eric Garside, VP of Engineering at Little Spoon",
            "industry": "Health & Nutrition / D2C",
        },
        {
            "quote": "I've literally had no issues, and that makes them my favorite vendor, full stop. If I have a problem, Lemon solves it, and they don't create any new problems in the process.",
            "author": "Eric Garside, VP of Engineering at Little Spoon",
            "industry": "Health & Nutrition / D2C",
        },
        {
            "quote": "I have an unwavering trust in Lemon. Every time I've asked for a role, they've given me resumes, we've reviewed them, we've hired somebody from them. We believe we have a 100% hit rate.",
            "author": "Eric Garside, VP of Engineering at Little Spoon",
            "industry": "Health & Nutrition / D2C",
        },
        {
            "quote": "The Lemon story, from my perspective, is one of great success. I'm a Lemon man now. I'd be dead in the water without them.",
            "author": "Eric Garside, VP of Engineering at Little Spoon",
            "industry": "Health & Nutrition / D2C",
        },
        {
            "quote": "Lemon was impressive from the first interaction. I recommend Lemon 100%. We couldn't have gotten RealEstateAPI to where it is today without Lemon – unless we completely burnt out our CTO.",
            "author": "Vince Harris, CEO of RealEstateAPI",
            "industry": "Real Estate / PropTech",
        },
        {
            "quote": "The resource is phenomenal. She has really become a part of our team. She does not feel like a contractor who is temporary.",
            "author": "Vince Harris, CEO of RealEstateAPI",
            "industry": "Real Estate / PropTech",
        },
        {
            "quote": "For the caliber of talent we're getting, I'd say Lemon is very reasonably priced.",
            "author": "Vince Harris, CEO of RealEstateAPI",
            "industry": "Real Estate / PropTech",
        },
        {
            "quote": "They have really good service, they operate with integrity, like we do, and that's what we respect and enjoy about them.",
            "author": "Vince Harris, CEO of RealEstateAPI",
            "industry": "Real Estate / PropTech",
        },
        # Additional testimonials from the index page
        {
            "quote": "I've worked with some incredible devs in my career, but the experience I am having with my dev through Lemon.io is incredible. I feel invincible as a founder.",
            "author": "Michele Serro, Founder of Doorsteps.co.uk, UK",
            "industry": "Real Estate",
        },
        {
            "quote": "I recommend Lemon to anyone looking for top-quality engineering talent. We previously worked with TopTal and many others, but Lemon gives us consistently incredible candidates.",
            "author": "Allie Fleder, Co-Founder & COO at SimplyWise, US",
            "industry": "FinTech",
        },
        {
            "quote": "I'm 2 weeks into working with a super legit dev on a critical project and he's meeting every expectation so far.",
            "author": "Francis Harrington, Founder at ProCloud Consulting, US",
            "industry": "Consulting",
        },
        {
            "quote": "Within week of engaging them I had 8 interviews lined up and was able to select not one but 2 new staff. I've been a hiring manager for 15 years and I can't believe how high quality it is!",
            "author": "Brent Maxwell, CEO at DEFY Labs, Australia",
            "industry": "Technology",
        },
        {
            "quote": "My lemon dev is incredible and gets things done fast. We're paying about $50/hr for an experienced full-stack dev. Way less than hiring a contractor in the states.",
            "author": "Anna Valkov McLaughlin, Director of Product at OnDiem, US",
            "industry": "Healthcare",
        },
        {
            "quote": "We've been working with Lemon since more than a year now. They always have been pretty quick to help us with resources and always very helpful to any of our questions.",
            "author": "Sonny Alves Dias, CTO at Pixelmatic, France & China",
            "industry": "Gaming",
        },
        {
            "quote": "Lemon.io was onboarded onto our project when we needed to flex our team to meet a tight go-live timeframe. The devs who joined us were skilled, collaborative and a real pleasure to work with.",
            "author": "Jabir Nathu, Entrepreneur at Cared Upon, Canada",
            "industry": "Social Impact",
        },
        {
            "quote": "The speed and precision of Lemon was the most impressive service. I did not expect to be connected with a high level developer so quickly with such great customer support.",
            "author": "Hugh Bartlett, Entrepreneur, US",
            "industry": "Technology",
        },
        {
            "quote": "I was looking to replace our lead python dev and just when I felt like giving up, lemon came to the rescue and matched us with one of the best hires we have ever made.",
            "author": "Laya Adib, CEO at ShopLook, US",
            "industry": "E-commerce / Fashion",
        },
        {
            "quote": "From the start, the Lemon.io team were responsive and helpful, compared to the other companies we contacted. Onboarding was smooth and we're really happy with how things are going.",
            "author": "Julie Matkin, Head of Product at Ctrl.io, Ireland",
            "industry": "Software",
        },
        {
            "quote": "Really great experience. I've hired from lemon quite a few times now and they've always been able to find the right developers in a very short period of time.",
            "author": "James Yu, Founder at jfyholdings.com, US",
            "industry": "Investment",
        },
        {
            "quote": "I work with them for almost 3 years. They always provide me with excellent programmers and complete all tasks in time. I can always trust them to complete tasks.",
            "author": "Guy Eyal, Owner at Coupa Media, Israel",
            "industry": "Media",
        },
    ]

    result = {
        "case_studies": studies,
        "testimonials": testimonials,
    }

    CASE_STUDIES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"  Saved {len(studies)} case studies + {len(testimonials)} testimonials to {CACHE_FILE}")
    return result


def get_case_studies() -> dict:
    """Load case studies, scraping if not cached."""
    return scrape_case_studies(force=False)
