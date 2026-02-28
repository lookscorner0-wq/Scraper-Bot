import warnings
warnings.filterwarnings('ignore')
import streamlit as st
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup
import re, time
from concurrent.futures import ThreadPoolExecutor, as_completed

SKIP = ['wikipedia.org','youtube.com','instagram.com','tiktok.com','github.com',
        'medium.com','blogspot.com','wordpress.com','twitter.com','facebook.com',
        'linkedin.com','reddit.com','amazon.com','ebay.com','pinterest.com',
        'microsoft.com','baidu.com','apple.com','google.com']

JUNK_EMAILS = ['@example','@test','@domain','@email','@site','@your','.png','.jpg',
               'noreply','no-reply','donotreply','unsubscribe','privacy@','abuse@']

def skip(url):
    return any(d in url for d in SKIP)

def get_emails(url):
    emails = set()
    def scrape(link):
        try:
            r = requests.get(link, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(r.text, 'html.parser')
            raw = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', soup.get_text())
            for e in map(str.lower, raw):
                if not any(j in e for j in JUNK_EMAILS):
                    emails.add(e)
            base = link.rstrip('/')
            for path in ['/contact', '/contact-us', '/about', '/support']:
                try:
                    r2 = requests.get(base + path, timeout=6, headers={'User-Agent': 'Mozilla/5.0'})
                    raw2 = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                                      BeautifulSoup(r2.text, 'html.parser').get_text())
                    for e in map(str.lower, raw2):
                        if not any(j in e for j in JUNK_EMAILS):
                            emails.add(e)
                except:
                    pass
        except:
            pass
    scrape(url)
    return list(emails)

def search_page(query, max_results):
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({'title': r.get('title', 'N/A'), 'url': r.get('href', '')})
        return results
    except Exception as e:
        st.error(f"❌ Search error: {e}")
        return []

def scrape_site(r):
    if skip(r['url']):
        return None
    emails = get_emails(r['url'])
    if not emails:
        return None
    return (r['title'], r['url'], ', '.join(emails))

# ── UI ───────────────────────────────────────────────
st.set_page_config(page_title="Contact Finder Bot", page_icon="🔍")
st.title("🔍 Contact Finder Bot")
st.caption("Enter a query and how many contacts you need.")

q = st.text_input("Search Query", placeholder="e.g. digital marketing agency UK")
n = st.number_input("Results Needed", min_value=1, max_value=20, value=4)

if st.button("🔍 Search"):
    if not q.strip():
        st.warning("Please enter a query.")
    else:
        found = []
        attempt = 1
        batch = n * 8
        max_attempts = 5

        status = st.empty()
        results_box = st.container()

        while len(found) < n and attempt <= max_attempts:
            status.info(f"🔄 Round {attempt} — {len(found)}/{n} found so far...")
            query = q if attempt == 1 else f"{q} contact email site"
            raw_results = search_page(query, batch * attempt)

            found_urls = {u for _, u, _ in found}
            fresh = [r for r in raw_results if r['url'] not in found_urls]

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(scrape_site, r): r for r in fresh}
                for future in as_completed(futures):
                    if len(found) >= n:
                        break
                    result = future.result()
                    if result:
                        found.append(result)
                        title, url, emails = result
                        with results_box:
                            st.success(f"[{len(found)}/{n}] **{title[:45]}**  \n🌐 {url}  \n📧 {emails}")

            attempt += 1
            time.sleep(1)

        status.empty()
        st.divider()
        if not found:
            st.error("❌ No contacts found. Try a different query.")
        elif len(found) < n:
            st.warning(f"⚠️ Only {len(found)}/{n} contacts found after {attempt-1} rounds.")
        else:
            st.success(f"✅ All {len(found)} contacts found!")
