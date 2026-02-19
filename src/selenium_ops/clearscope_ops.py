"""Clearscope automation: draft creation, term extraction, article grading.

Handles login via manual browser auth, then automates all Clearscope
interactions within a single browser session.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from src.config import CLEARSCOPE_DIR, CLEARSCOPE_WORKSPACE


class ClearscopeAutomation:
    """Full Clearscope automation: create drafts, scrape terms, validate articles."""

    def __init__(self, headless: bool = False):
        self.driver = None
        self.headless = headless
        self._logged_in = False
        self.workspace = CLEARSCOPE_WORKSPACE

    # ── Browser lifecycle ─────────────────────────────────────────────

    def start(self):
        """Launch browser and wait for user to log in to Clearscope."""
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options

        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except Exception:
            service = Service()

        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")

        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)

        self.driver.get(f"https://www.clearscope.io/{self.workspace}/drafts")

        print("\n" + "=" * 50)
        print("CLEARSCOPE LOGIN REQUIRED")
        print("=" * 50)
        print("Log in to Clearscope in the browser window.")
        print("DO NOT close the browser window — keep it open.")
        input("Press Enter here once you're logged in... ")
        self._logged_in = True

    @property
    def is_alive(self) -> bool:
        """Check if the browser window is still open."""
        if not self.driver:
            return False
        try:
            _ = self.driver.current_url
            return True
        except Exception:
            return False

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # ── Draft creation ────────────────────────────────────────────────

    def create_drafts_batch(
        self,
        keywords: list[str],
        content_urls: list[str] | None = None,
    ) -> tuple[list[str], int]:
        """Create multiple drafts at once via the batch form.

        Uses "Create Multiple Drafts" with Search Queries + Content URLs textareas.
        Returns (draft_urls, num_newly_created) — URLs in keyword order, count of
        drafts actually created (vs skipped as pre-existing).
        """
        if not self.is_alive:
            raise RuntimeError("Browser window is closed. Restart the script.")

        from selenium.webdriver.common.by import By

        if not keywords:
            return [], 0

        content_urls = content_urls or []
        # Pad with empty strings so we have one URL per keyword (or empty for extras)
        while len(content_urls) < len(keywords):
            content_urls.append("")

        # Pre-check: go to drafts list and skip keywords that already have drafts
        drafts_url = f"https://www.clearscope.io/{self.workspace}/drafts"
        self.driver.get(drafts_url)
        time.sleep(3)
        existing_map = self._get_existing_drafts_map()
        keywords_to_create = []
        content_urls_to_create = []
        for kw, url in zip(keywords, content_urls[: len(keywords)]):
            if kw.lower() not in existing_map:
                keywords_to_create.append(kw)
                content_urls_to_create.append(url)
            else:
                pass  # skip — draft exists

        if existing_map:
            skipped = sum(1 for kw in keywords if kw.lower() in existing_map)
            if skipped:
                print(f"  Skipping {skipped} keywords that already have Clearscope drafts")

        if not keywords_to_create:
            return [existing_map.get(kw.lower(), "") for kw in keywords], 0

        batch_url = f"https://www.clearscope.io/{self.workspace}/drafts/batch/new"
        self.driver.get(batch_url)
        time.sleep(3)

        # Fill Search Queries textarea (forms_drafts_batch[qs])
        queries_text = "\n".join(keywords_to_create)
        queries_sel = [
            "#forms_drafts_batch_qs",
            "textarea[name='forms_drafts_batch[qs]']",
        ]
        queries_ta = None
        for sel in queries_sel:
            try:
                queries_ta = self.driver.find_element(By.CSS_SELECTOR, sel)
                if queries_ta and queries_ta.is_displayed():
                    break
            except Exception:
                continue
        if not queries_ta:
            print("  WARNING: Could not find Search Queries textarea")
            return [], 0
        queries_ta.clear()
        queries_ta.send_keys(queries_text)

        # Fill Content URLs textarea (forms_drafts_batch[extract_urls])
        urls_text = "\n".join(content_urls_to_create)
        urls_sel = [
            "#forms_drafts_batch_extract_urls",
            "textarea[name='forms_drafts_batch[extract_urls]']",
        ]
        urls_ta = None
        for sel in urls_sel:
            try:
                urls_ta = self.driver.find_element(By.CSS_SELECTOR, sel)
                if urls_ta and urls_ta.is_displayed():
                    break
            except Exception:
                continue
        if urls_ta and urls_text.strip():
            urls_ta.clear()
            urls_ta.send_keys(urls_text)

        # Click Create Drafts button
        submit_btn = None
        for sel in [
            "button[type='submit']",
            "button.btn-primary",
        ]:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed() and "Create" in (btn.text or ""):
                    submit_btn = btn
                    break
            except Exception:
                continue
        if not submit_btn:
            print("  WARNING: Could not find Create Drafts button")
            return [], 0

        # Scroll into view and use JS click to avoid overlay intercepting (ElementClickInterceptedException)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
        time.sleep(0.3)
        self.driver.execute_script("arguments[0].click();", submit_btn)
        print(f"  Batch submitted ({len(keywords_to_create)} drafts)...")
        time.sleep(15)  # Batch creation can take a while

        # Scrape new draft URLs from drafts list (match by keyword)
        self.driver.get(drafts_url)
        time.sleep(5)
        new_urls = self._scrape_draft_urls_from_list(keywords=keywords_to_create)

        # Merge: existing + newly created, in original keyword order
        new_idx = 0
        result = []
        for kw in keywords:
            if kw.lower() in existing_map:
                result.append(existing_map[kw.lower()])
            else:
                result.append(new_urls[new_idx] if new_idx < len(new_urls) else "")
                new_idx += 1
        if len(result) != len(keywords):
            print(f"  NOTE: Found {len(result)} draft URLs for {len(keywords)} keywords")
        return result, len(keywords_to_create)

    def _drafts_page_url(self, page: int) -> str:
        """Build drafts list URL for a given page, preserving existing query params (e.g. p=)."""
        url = self.driver.current_url
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params["page"] = [str(page)]
        query = urlencode(params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))

    def _scrape_draft_rows_from_current_page(self) -> list[tuple[str, str]]:
        """Scrape draft (query_lower, href) from current page. Returns list of (query, url)."""
        from selenium.webdriver.common.by import By

        rows = []
        for a in self.driver.find_elements(
            By.CSS_SELECTOR, "table a.link-primary[href*='/drafts/']"
        ):
            try:
                href = a.get_attribute("href") or ""
                if "/drafts/batch" in href or "/drafts/new" in href:
                    continue
                if not re.search(r"/drafts/[a-zA-Z0-9]+(?:/|$|\?)", href):
                    continue
                query = (a.text or "").strip().lower()
                if query:
                    rows.append((query, href))
            except Exception:
                continue
        return rows

    def _get_existing_drafts_map(self) -> dict[str, str]:
        """Scrape the drafts list (all pages) and return keyword_lower -> url (first = newest)."""
        out: dict[str, str] = {}
        page = 1
        while True:
            if page > 1:
                self.driver.get(self._drafts_page_url(page))
                time.sleep(2)
            rows = self._scrape_draft_rows_from_current_page()
            for query, href in rows:
                if query not in out:
                    out[query] = href
            if not rows:
                break
            page += 1
        return out

    def _scrape_draft_urls_from_list(
        self,
        keywords: list[str] | None = None,
        limit: int = 100,
    ) -> list[str]:
        """Scrape draft URLs from the drafts list (all pages).

        When keywords is provided, matches by Query column (a.link-primary) and returns
        URLs in the same order as keywords. Paginates through all pages to find matches.
        When not provided, returns newest N URLs from first page only.
        """
        from selenium.webdriver.common.by import By

        if keywords:
            keyword_to_urls: dict[str, list[str]] = {}
            page = 1
            while True:
                if page > 1:
                    self.driver.get(self._drafts_page_url(page))
                    time.sleep(2)
                rows = self._scrape_draft_rows_from_current_page()
                for query, href in rows:
                    keyword_to_urls.setdefault(query, []).append(href)
                if not rows:
                    break
                page += 1
            # Assign by submission order: first submitted = oldest = pop from end
            result = []
            for kw in keywords:
                lst = keyword_to_urls.get(kw.lower(), [])
                result.append(lst.pop() if lst else "")
            return result

        # No keywords: just first page, up to limit
        urls = []
        for a in self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/drafts/']"):
            try:
                href = a.get_attribute("href") or ""
                if "/drafts/batch" in href or "/drafts/new" in href:
                    continue
                if re.search(r"/drafts/[a-zA-Z0-9_-]+(?:[?&]|$)", href) and href not in urls:
                    urls.append(href)
                    if len(urls) >= limit:
                        break
            except Exception:
                continue
        return urls[:limit]

    def create_draft(self, keyword: str) -> str | None:
        """Create a new Clearscope draft for a keyword.

        Clicks the "Create Draft" link (a.btn-primary), waits for the new
        draft editor to load, then looks for a keyword/topic input field
        to associate it with the target keyword.

        Returns the draft URL if successful, None otherwise.
        """
        if not self.is_alive:
            raise RuntimeError("Browser window is closed. Restart the script.")

        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        drafts_url = f"https://www.clearscope.io/{self.workspace}/drafts"
        self.driver.get(drafts_url)
        time.sleep(3)

        # The "Create Draft" button: <a class="btn-primary" href="/.../drafts/new?p=...">
        create_link = None
        for selector in [
            "a.btn-primary[href*='/drafts/new']",
            "a.btn-primary",
            "a[href*='/drafts/new']",
        ]:
            try:
                create_link = self.driver.find_element(By.CSS_SELECTOR, selector)
                if create_link and create_link.is_displayed():
                    break
                create_link = None
            except Exception:
                continue

        if not create_link:
            print(f"  WARNING: Could not find 'Create Draft' link.")
            print(f"  Page: {self.driver.current_url}")
            return None

        create_link.click()
        time.sleep(3)

        # Now on Create Draft form: Search Query field is forms_draft[q] (id=forms_draft_q)
        keyword_selectors = [
            "#forms_draft_q",
            "input[name='forms_draft[q]']",
            "input[name*='forms_draft']",
            "input[placeholder*='keyword' i]",
            "input[placeholder*='topic' i]",
            "input[placeholder*='query' i]",
        ]

        keyword_input = None
        for selector in keyword_selectors:
            try:
                inp = self.driver.find_element(By.CSS_SELECTOR, selector)
                if inp and inp.is_displayed():
                    keyword_input = inp
                    break
            except Exception:
                continue

        if not keyword_input:
            print(f"  WARNING: Could not find Search Query input (forms_draft_q)")
            current_url = self.driver.current_url
            if "/drafts/" in current_url:
                return current_url
            return None

        keyword_input.clear()
        keyword_input.send_keys(keyword)
        keyword_input.send_keys(Keys.RETURN)
        print(f"  Submitted keyword: {keyword}")
        time.sleep(5)

        draft_url = self.driver.current_url
        if "/drafts/" not in draft_url:
            print(f"  WARNING: Expected draft URL after submit, got: {draft_url}")
        else:
            print(f"  Draft created: {draft_url}")
        return draft_url

    # ── Term extraction ───────────────────────────────────────────────

    def scrape_terms(self, draft_url: str) -> list[dict]:
        """Navigate to a Clearscope draft and scrape the terms list."""
        if not self.driver:
            raise RuntimeError("Call start() first.")

        from selenium.webdriver.common.by import By

        self.driver.get(draft_url)
        print(f"  Loading Clearscope draft...")
        time.sleep(5)

        self._bypass_entrance_page()

        terms = []

        # Try multiple extraction strategies
        for strategy_name, strategy_fn in [
            ("DOM elements", self._extract_terms_from_dom),
            ("page data", self._extract_terms_from_page_data),
            ("visible text", self._extract_terms_from_text),
        ]:
            try:
                terms = strategy_fn()
                if terms:
                    break
            except Exception as e:
                print(f"  {strategy_name} extraction failed: {e}")

        if terms:
            print(f"  Extracted {len(terms)} terms")
        else:
            print(f"  WARNING: Could not extract terms. Selectors may need updating.")
            print(f"  Page title: {self.driver.title}")

        return terms

    def _bypass_entrance_page(self):
        """Detect and dismiss the entrance page shown on first draft visit.

        Selects 'Start from a blank Draft' (value="0") and clicks 'Get started'.
        """
        if "/entrance" not in self.driver.current_url:
            return

        from selenium.webdriver.common.by import By

        print("  Entrance page detected — selecting 'Start from a blank Draft'...")

        try:
            blank_radio = self.driver.find_element(
                By.CSS_SELECTOR,
                "input[name='forms_drafts_entrance[entrance]'][value='0']",
            )
            self.driver.execute_script("arguments[0].click();", blank_radio)
            time.sleep(0.5)

            submit_btn = self.driver.find_element(
                By.CSS_SELECTOR, "button[type='submit']"
            )
            self.driver.execute_script("arguments[0].click();", submit_btn)
        except Exception:
            return

        time.sleep(5)

    def _extract_terms_from_dom(self) -> list[dict]:
        from selenium.webdriver.common.by import By

        terms = []

        term_elements = self.driver.find_elements(
            By.CSS_SELECTOR, '[data-editor-target="term"]'
        )

        for el in term_elements:
            try:
                sortable_json = el.get_attribute("data-sortable-values") or ""
                if not sortable_json:
                    continue
                sortable = json.loads(sortable_json)

                term_name = sortable.get("primary_variant", "").strip()
                if not term_name:
                    continue

                importance = str(sortable.get("importance", 5))

                uses_min, uses_max = 1, 2
                try:
                    uses_el = el.find_element(
                        By.CSS_SELECTOR, "div.text-on-surface-variant.text-xs"
                    )
                    uses_text = uses_el.text or ""
                    uses_match = re.search(r'Typical uses:\s*(\d+)\s*[-–]\s*(\d+)', uses_text)
                    if uses_match:
                        uses_min = int(uses_match.group(1))
                        uses_max = int(uses_match.group(2))
                except Exception:
                    pass

                variants = []
                try:
                    variant_el = el.find_element(
                        By.CSS_SELECTOR, "div.italic.text-on-surface-variant"
                    )
                    variant_text = (variant_el.text or "").strip()
                    if variant_text:
                        variants = [v.strip() for v in variant_text.split(",") if v.strip()]
                except Exception:
                    pass

                terms.append({
                    "term": term_name,
                    "variants": variants,
                    "importance": importance,
                    "typical_uses_min": uses_min,
                    "typical_uses_max": uses_max,
                    "current_uses": 0,
                })
            except (json.JSONDecodeError, Exception):
                continue

        return terms

    def _extract_terms_from_page_data(self) -> list[dict]:
        scripts_to_try = [
            "return window.__NEXT_DATA__",
            "return window.__APP_STATE__",
            "return window.__INITIAL_STATE__",
        ]

        for script in scripts_to_try:
            try:
                data = self.driver.execute_script(script)
                if data:
                    return self._extract_terms_from_json(data)
            except Exception:
                continue

        from selenium.webdriver.common.by import By
        script_tags = self.driver.find_elements(By.TAG_NAME, "script")
        for tag in script_tags:
            inner = tag.get_attribute("innerHTML") or ""
            if "Primary Variant" in inner or "importance" in inner:
                try:
                    json_match = re.search(r'\{.*"terms".*\}', inner, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                        return self._extract_terms_from_json(data)
                except (json.JSONDecodeError, AttributeError):
                    continue

        return []

    def _extract_terms_from_json(self, data) -> list[dict]:
        terms = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and ("term" in item or "Primary Variant" in item):
                    term = item.get("term") or item.get("Primary Variant", "")
                    if term:
                        terms.append({
                            "term": term.strip(),
                            "variants": _split_variants(
                                item.get("variants") or item.get("Secondary Variants", "")
                            ),
                            "importance": str(
                                item.get("importance") or item.get("Importance", "5")
                            ).split("/")[0].strip(),
                            "typical_uses_min": int(
                                item.get("typical_uses_min") or item.get("Typical Uses Min", 1) or 1
                            ),
                            "typical_uses_max": int(
                                item.get("typical_uses_max") or item.get("Typical Uses Max", 2) or 2
                            ),
                            "current_uses": 0,
                        })
                elif isinstance(item, (dict, list)):
                    terms.extend(self._extract_terms_from_json(item))
        elif isinstance(data, dict):
            for value in data.values():
                if isinstance(value, (dict, list)):
                    terms.extend(self._extract_terms_from_json(value))
        return terms

    def _extract_terms_from_text(self) -> list[dict]:
        from selenium.webdriver.common.by import By

        body = self.driver.find_element(By.TAG_NAME, "body")
        page_text = body.text

        terms = []
        blocks = re.split(r'\n(?=\d+\.\s)', page_text)
        for block in blocks:
            if not block.strip():
                continue
            parsed = self._parse_term_text(block)
            if parsed:
                terms.append(parsed)
        return terms

    def _parse_term_text(self, text: str) -> dict | None:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            return None

        term_name = re.sub(r'^\d+\.\s*', '', lines[0]).strip()
        if not term_name or len(term_name) > 100:
            return None

        importance = "5"
        uses_min = 1
        uses_max = 2
        variants = []

        for line in lines[1:]:
            imp_match = re.search(r'(?:importance|Importance)\s*[:\s]*(\d+)/10', line)
            if imp_match:
                importance = imp_match.group(1)

            uses_match = re.search(
                r'(?:typical\s+uses|Typical\s+Uses)[:\s]*(\d+)\s*[-–]\s*(\d+)',
                line, re.IGNORECASE,
            )
            if uses_match:
                uses_min = int(uses_match.group(1))
                uses_max = int(uses_match.group(2))

            variant_match = re.search(r'(?:also|variants?)[:\s]+(.*)', line, re.IGNORECASE)
            if variant_match:
                variants = [v.strip() for v in variant_match.group(1).split(",") if v.strip()]

        return {
            "term": term_name,
            "variants": variants,
            "importance": importance,
            "typical_uses_min": uses_min,
            "typical_uses_max": uses_max,
            "current_uses": 0,
        }

    # ── Article validation ────────────────────────────────────────────

    def paste_and_grade(self, draft_url: str, article_text: str) -> str | None:
        """Paste article into Clearscope editor and read grade."""
        if not self.driver:
            raise RuntimeError("Call start() first.")

        from selenium.webdriver.common.by import By

        self.driver.get(draft_url)
        time.sleep(3)

        editor_selectors = [
            "[contenteditable='true']",
            ".ProseMirror",
            "[class*='editor']",
            "[role='textbox']",
        ]

        editor = None
        for selector in editor_selectors:
            try:
                editor = self.driver.find_element(By.CSS_SELECTOR, selector)
                if editor:
                    break
            except Exception:
                continue

        if not editor:
            print("  WARNING: Could not find Clearscope editor element.")
            return None

        try:
            self.driver.execute_script(
                "arguments[0].innerHTML = arguments[1]", editor, article_text
            )
            self.driver.execute_script("""
                var el = arguments[0];
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, editor)
        except Exception as e:
            print(f"  WARNING: Could not paste article ({e})")
            return None

        print("  Waiting for Clearscope grade calculation...")
        time.sleep(10)

        grade_selectors = [
            "[class*='grade'], [class*='Grade']",
            "[class*='score'], [class*='Score']",
            "[class*='content-grade']",
        ]

        for selector in grade_selectors:
            try:
                grade_el = self.driver.find_element(By.CSS_SELECTOR, selector)
                grade_text = grade_el.text.strip()
                if grade_text and len(grade_text) <= 3:
                    print(f"  Clearscope grade: {grade_text}")
                    return grade_text
            except Exception:
                continue

        body_text = self.driver.find_element(By.TAG_NAME, "body").text
        grade_match = re.search(r'Content grade\s*\n?\s*([A-F][+-]?)', body_text)
        if grade_match:
            grade = grade_match.group(1)
            print(f"  Clearscope grade: {grade}")
            return grade

        print("  WARNING: Could not extract Clearscope grade.")
        return None

    # ── Cache management ──────────────────────────────────────────────

    def save_terms(self, slug: str, terms: list[dict]):
        CLEARSCOPE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = CLEARSCOPE_DIR / f"{slug}.json"
        cache_path.write_text(json.dumps(terms, indent=2))
        print(f"  Cached {len(terms)} terms to {cache_path}")

    @staticmethod
    def terms_cached(slug: str) -> bool:
        json_path = CLEARSCOPE_DIR / f"{slug}.json"
        csv_path = CLEARSCOPE_DIR / f"{slug}.csv"
        return json_path.exists() or csv_path.exists()


def _split_variants(raw) -> list[str]:
    if isinstance(raw, list):
        return raw
    if not raw:
        return []
    return [v.strip() for v in str(raw).replace(";", ",").split(",") if v.strip()]
