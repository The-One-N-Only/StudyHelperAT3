import requests
from bs4 import BeautifulSoup
import src.whitelist as whitelist

USER_AGENT = "StudyLib/1.0 (Academic Research Assistant)"

def fetch_source(url):
    if not whitelist.is_allowed(url):
        raise ValueError("URL not allowed")
    
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=5)
        if resp.status_code != 200:
            return {"status": False, "error": "Failed to load source"}
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        # Remove unwanted tags
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'iframe', 'form']):
            tag.decompose()
        
        title = soup.title.string if soup.title else ""
        html = str(soup.body) if soup.body else str(soup)
        text = soup.get_text(separator=' ', strip=True)
        
        # Check for paywall
        if any(word in resp.text.lower() for word in ['login', 'subscribe', 'paywall', 'access denied']):
            return {"status": False, "error": "This source could not be loaded — it may be paywalled or require login.", "fallback_url": url}
        
        return {
            "status": True,
            "html": html,
            "text": text,
            "title": title,
            "url": url,
            "domain": whitelist.get_domain(url)
        }
    except requests.Timeout:
        return {"status": False, "error": "Request timed out"}
    except:
        return {"status": False, "error": "Failed to fetch source"}