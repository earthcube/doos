# /// script
# dependencies = [
#   "dspy",
#   "mcp2py",
#   "fastmcp",
# ]
# ///

import os
import dspy
from mcp2py import load

# Set up Grok 4 fast LM
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY environment variable not set")

lmor = dspy.LM(
    model="openrouter/x-ai/grok-4-fast",
    api_base="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    cache=False,
    temperature=0.5,
)

dspy.configure(lm=lmor)

# Load MCP server for LanceMcpPredict tool
api = load("http://homelab.lan:8898/mcp")


class GfuDocsSkill(dspy.Signature):
    """Types from the graph."""

    query: str = dspy.InputField(desc="The search query for GFU docs")
    answer: str = dspy.OutputField(
        desc="The final answer from Grok based on the search context"
    )


class GfuDocsModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.ReAct(GfuDocsSkill, tools=api.tools)

    def forward(self, query: str):
        result = self.predict(query=query)
        return result


# Example usage
if __name__ == "__main__":
    skill = GfuDocsModule()
    query = "What types are in the graph?"
    result = skill(query=query)
    print(result.answer)
