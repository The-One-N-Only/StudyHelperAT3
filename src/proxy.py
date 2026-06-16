import requests
from bs4 import BeautifulSoup
import src.whitelist as whitelist

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}
READER_DOMAINS = {"web.md", "pubmed.ncbi.nlm.nih.gov"}
GOOGLE_BOOKS_DOMAINS = {"books.google.com"}
READER_DOMAIN_SUFFIXES = (
    ".gov.uk",
    ".nhs.uk",
    ".gov.au",
    ".ac.uk",
)


def is_reader_domain(domain: str) -> bool:
    if domain in READER_DOMAINS:
        return True
    return any(domain.endswith(suffix) for suffix in READER_DOMAIN_SUFFIXES)


def is_google_books_domain(domain: str) -> bool:
    return domain in GOOGLE_BOOKS_DOMAINS


def build_reader_html(soup, url: str) -> str:
    if soup.head and soup.head.find('base') is None:
        base_tag = soup.new_tag('base', href=url)
        soup.head.insert(0, base_tag)

    if soup.body:
        return ''.join(str(child) for child in soup.body.contents)
    return str(soup)


def fetch_source(url):
    if not whitelist.is_allowed(url):
        raise ValueError("URL not allowed")
    
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        if resp.status_code != 200:
            if resp.status_code in (403, 429):
                return {"status": False, "error": "Source blocked by the remote site. Open it directly in a new tab.", "fallback_url": url}
            return {"status": False, "error": "Failed to load source"}
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        # Remove unwanted tags but keep CSS and link tags so page styling survives.
        for tag in soup(['script', 'nav', 'header', 'footer', 'iframe', 'form']):
            tag.decompose()

        title = soup.title.string if soup.title else ""
        text = soup.get_text(separator=' ', strip=True)
        domain = whitelist.get_domain(url)

        mode = 'iframe'
        if is_google_books_domain(domain):
            mode = 'google_books'
        elif is_reader_domain(domain):
            mode = 'reader'

        reader_html = ''
        if mode == 'reader':
            reader_html = build_reader_html(soup, url)
        else:
            if soup.head and soup.head.find('base') is None:
                base_tag = soup.new_tag('base', href=url)
                soup.head.insert(0, base_tag)

        html = reader_html if mode == 'reader' else str(soup)

        if mode == 'google_books':
            html = (
                '<div class="proxy-google-books p-4">'
                '<h5>Google Books preview</h5>'
                '<p>Book preview pages are not rendered directly inside StudyHelper.</p>'
                '<a href="{url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm">Open Google Books</a>'
                '</div>'.format(url=url)
            )

        # Check for paywall using stricter phrases only, but skip Wikipedia pages.
        if domain and domain.endswith('wikipedia.org'):
            return {
                "status": True,
                "html": html,
                "text": text,
                "title": title,
                "url": url,
                "domain": domain,
                "mode": mode
            }

        cleaned_text = text.lower()
        if 'checking your browser before accessing' in cleaned_text or 'just a moment' in cleaned_text or 'cf-ray' in cleaned_text or 'cloudflare' in cleaned_text:
            return {"status": False, "error": "Source blocked by remote site protection. Open it directly in a new tab.", "fallback_url": url}

        paywall_indicators = [
            'paywall',
            'access denied',
            'subscription required',
            'subscribe to continue',
            'sign in to continue',
            'log in to continue',
            'please sign in',
            'please login',
            'sign in to view',
            'this content is for subscribers only',
            'join now to read',
            'subscription required to view',
            'you need to sign in'
        ]
        if any(phrase in cleaned_text for phrase in paywall_indicators):
            return {"status": False, "error": "This source could not be loaded — it may be paywalled or require login.", "fallback_url": url}
        
        return {
            "status": True,
            "html": html,
            "text": text,
            "title": title,
            "url": url,
            "domain": domain,
            "mode": mode
        }
    except requests.Timeout:
        return {"status": False, "error": "Request timed out"}
    except:
        return {"status": False, "error": "Failed to fetch source"}