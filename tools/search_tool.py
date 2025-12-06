from duckduckgo_search import DDGS

class SearchTool:
    """
    Performs a web search using DuckDuckGo (No API Key required).
    """
    definition = {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for current news, events, or facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."}
                },
                "required": ["query"]
            }
        }
    }

    @staticmethod
    def execute(query: str):
        try:
            # We fetch 5 results to mimic the 'valves' setting
            results = DDGS().text(keywords=query, max_results=5)
            if not results:
                return "No results found."
            
            # Format cleanly for the LLM
            formatted_results = []
            for r in results:
                formatted_results.append(f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}\n---")
            
            return "\n".join(formatted_results)
        except Exception as e:
            return f"Search Error: {str(e)}"
        