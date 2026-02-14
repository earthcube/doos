import os
from pathlib import Path

from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import OpenAI  # Or use ChatOpenAI for better performance
import pandas as pd

# Load the CSV file into a Pandas DataFrame Ref: https://www.bco-dmo.org/doi/dataset/10.26008/1912/bco-dmo.990510.1
csv_path = Path(__file__).parent / '990510_v1_gp17-oce_d13c_dic.csv'
if not csv_path.exists():
    raise FileNotFoundError(f"CSV file not found: {csv_path}")

df = pd.read_csv(csv_path)

# Get API key from environment variable
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

# Run the agent with the query (using invoke instead of deprecated run)
result = agent.invoke({"input": query})

# Print the result
print(result["output"])