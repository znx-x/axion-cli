import requests
from bs4 import BeautifulSoup
import json

class FetchTool:
    """
    Retrieves the contents of a URL and returns a human-readable string.
    Ported from ZNX's Open WebUI Tool.
    """
    definition = {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Visit a specific URL and read its content (scrape).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The http/https URL to visit."}
                },
                "required": ["url"]
            }
        }
    }

    @staticmethod
    def _html_to_text(html: str) -> str:
        """Strip HTML tags, collapse whitespace and return readable text."""
        soup = BeautifulSoup(html, "lxml")
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()

        text = soup.get_text(separator="\n")
        # Remove empty lines and strip each line
        cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        return cleaned[:8000] # Truncate to prevent context overflow

    @staticmethod
    def execute(url: str):
        if not url.startswith(("http://", "https://")):
            return "Error: URL must begin with http:// or https://"

        headers = {
            "User-Agent": "Axion-CLI/3.0",
            "Accept": "text/html,application/json,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            
            content_type = resp.headers.get("Content-Type", "").lower()
            raw = resp.text

            if "application/json" in content_type:
                try:
                    return json.dumps(json.loads(raw), indent=2)
                except:
                    return raw
            elif "text/html" in content_type:
                return FetchTool._html_to_text(raw)
            else:
                return raw[:1000] + "..."

        except Exception as e:
            return f"[Error] Unable to retrieve URL: {str(e)}"
        