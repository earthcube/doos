import os
from pathlib import Path
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import OpenAI  # Or use ChatOpenAI for better performance
import pandas as pd
import json
import threading
from playwright.sync_api import sync_playwright

# This is a hack for now, thinking of replacing with loading the JSON-LD into oxigraph and doing a simple
# SPARQL query, since that will not be too heavy and will more accurate I think.
def get_csv_urls(json_ld: dict) -> list[str]:
    """Extract contentUrl values ending in .csv from JSON-LD distribution property."""
    distribution = json_ld.get("distribution", [])
    return [
        item["contentUrl"]
        for item in distribution
        if item.get("contentUrl", "").endswith(".csv")
    ]

def get_json_ld(url: str) -> list:
    results = []

    def run():
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")

            json_ld_docs = page.evaluate("""() => {
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                return Array.from(scripts).map(s => {
                    try { return JSON.parse(s.textContent); }
                    catch { return null; }
                }).filter(Boolean);
            }""")

            browser.close()
            results.extend(json_ld_docs)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    return results

test_url = "https://www.bco-dmo.org/doi/dataset/10.26008/1912/bco-dmo.990510.1"
json_ld = get_json_ld(test_url)
# print(json.dumps(results, indent=2))

csv_urls = get_csv_urls(json_ld[0])

if not csv_urls:
    raise ValueError("No CSV URLs found in JSON-LD distribution")

df = pd.read_csv(csv_urls[0])

# Get the API key from the environment variable
api_key = os.environ.get("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("OPENROUTER_API_KEY environment variable is not set")

# Initialize the LLM with OpenRouter (use ChatOpenAI for more advanced models)
llm = OpenAI(
    temperature=0,
    openai_api_key=api_key,
    base_url="https://openrouter.ai/api/v1",  # Updated from deprecated openai_api_base
    model="openai/gpt-3.5-turbo-instruct"  # Specify a model available on OpenRouter; adjust as needed
    # model="x-ai/grok-4.1-fast"
)

# Create the Pandas DataFrame agent
agent = create_pandas_dataframe_agent(llm, df, verbose=True, allow_dangerous_code=True)

# Define the natural language query for the agent
query = """
First, list all column headers in the DataFrame.
Then, identify columns that seem related to 'depth' by checking if the word 'depth' (case-insensitive) appears in the column name.
Note that depth might always be exactly spelled out or be part of a composite variable name.  Also look for pressure 
related columns as they can be used as a proxy for depth.  
For each identified depth-related column, calculate and return the minimum, maximum values.
Format the output as a dictionary where keys are column names and values are another dict with 'min', 'max', 'mean', 'mode'.
If no depth-related columns are found, return an empty dict.
"""

# Run the agent with the query (using "invoke" instead of deprecated run)
result = agent.invoke({"input": query})

# Print the result
print(result["output"])