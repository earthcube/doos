import dspy
import requests
from urllib.parse import quote_plus

# 1. Configure your LLM (use any OpenAI-compatible endpoint)
lm = dspy.LM("openai/gpt-4o", max_tokens=2000)   # or grok, claude, local, etc.
dspy.configure(lm=lm)

# 2. BCO-DMO Tools (using their excellent ERDDAP server – the primary programmatic interface)
def search_bcodmo_datasets(query: str, max_results: int = 8) -> str:
    """
    Search BCO-DMO for oceanographic datasets using ERDDAP.
    Returns formatted list of dataset IDs, titles, short summaries, and direct links.
    Use this first for any marine/bio/chem data query.
    """
    try:
        encoded = quote_plus(query)
        url = f"https://erddap.bco-dmo.org/erddap/search/index.json?page=1&itemsPerPage={max_results}&searchFor={encoded}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()

        table = data.get("table", {})
        cols = table.get("columnNames", [])
        rows = table.get("rows", [])

        results = [f"BCO-DMO ERDDAP search for '{query}' → {len(rows)} results:\n"]
        for row in rows[:max_results]:
            item = dict(zip(cols, row))
            ds_id = item.get("Dataset ID", "N/A")
            title = item.get("Title", "N/A")
            summary = (item.get("Summary", "N/A")[:350] + "...") if len(item.get("Summary", "")) > 350 else item.get("Summary", "N/A")
            info_url = item.get("Info", "N/A")
            data_url = item.get("tabledap", "N/A") or item.get("Data Access", "N/A")

            results.append(f"• Dataset ID: {ds_id}")
            results.append(f"  Title: {title}")
            results.append(f"  Summary: {summary}")
            results.append(f"  Metadata: {info_url}")
            if data_url and data_url != "N/A":
                results.append(f"  Data: {data_url}")
            results.append("---")

        return "\n".join(results)
    except Exception as e:
        return f"BCO-DMO search error: {str(e)}"


def fetch_bcodmo_data(dataset_id: str, variables: str = "*", limit: int = 50, extra_constraints: str = "") -> str:
    """
    Fetch actual data (or preview) from a specific BCO-DMO dataset via ERDDAP tabledap.
    variables = comma-separated list or "*" for all. Add constraints like "&time>=2020-01-01T00:00:00Z".
    Returns first N rows as CSV (truncated) + summary.
    """
    try:
        base = f"https://erddap.bco-dmo.org/erddap/tabledap/{dataset_id}.csv"
        url = f"{base}?{variables}{extra_constraints}&limit={limit}"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        text = r.text
        lines = text.splitlines()
        preview = "\n".join(lines[:limit + 2])  # header + data
        return f"Dataset {dataset_id} preview ({len(lines)-1} total rows returned):\n{preview}\n\n[truncated at {limit} rows]"
    except Exception as e:
        return f"Data fetch error for {dataset_id}: {str(e)}"


# 3. Optional general web tools (highly recommended for "deep" research)
# Use Tavily (best for research – get free API key at tavily.com) or duckduckgo-search
from tavily import TavilyClient   # pip install tavily-python

tavily = TavilyClient(api_key="your-tavily-key")

def web_search_tavily(query: str, max_results: int = 10) -> str:
    """General web search with high-quality results and summaries. Use for literature, context, or non-BCO-DMO sources."""
    try:
        results = tavily.search(query=query, max_results=max_results, search_depth="advanced")
        out = [f"Web search for '{query}':"]
        for r in results["results"]:
            out.append(f"• {r['title']}\n  {r['url']}\n  {r['content'][:300]}...")
        return "\n\n".join(out)
    except Exception as e:
        return f"Web search error: {str(e)}"

# 4. The Research Agent (core of your deep-seek tool)
class OceanResearchAgent(dspy.Module):
    def __init__(self, max_iters: int = 10):
        super().__init__()
        self.react = dspy.ReAct(
            signature="research_query: str -> comprehensive_report: str, key_findings: list[str], sources: list[str]",
            tools=[
                search_bcodmo_datasets,
                fetch_bcodmo_data,
                web_search_tavily,
                # add more: browse specific URL, calculator, etc.
            ],
            max_iters=max_iters
        )

    def forward(self, research_query: str):
        result = self.react(research_query=research_query)
        return result

# Usage
agent = OceanResearchAgent(max_iters=12)

response = agent(research_query="What are the latest dissolved oxygen and chlorophyll datasets from the North Atlantic in BCO-DMO? Compare with recent papers.")
print(response.comprehensive_report)
print("\nKey findings:", response.key_findings)
print("\nSources:", response.sources)
