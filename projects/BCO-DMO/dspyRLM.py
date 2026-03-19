import dspy  # DSPy is the foundation
# from rlm import RLM  # The RLM implementation on top of DSPy
import os
import warnings
from pathlib import Path
from typing import Dict, List
import json

import datetime
warnings.filterwarnings('ignore', message='Unable to find the Deno cache dir')

dspy.configure_cache(
    enable_disk_cache=False,
    enable_memory_cache=False
)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
NRP_API_KEY = os.environ['NRP_API_KEY']

# Using OpenRouter
lm = dspy.LM(
    model="openrouter/openai/gpt-5",
    # model = "openai/gpt-3.5-turbo-instruct",  # Specify a model available on OpenRouter; adjust as needed
    api_base="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    cache=False,
    temperature=0
)

# # Using NRP
# lm = dspy.LM(
#     # model="custom_openai/kimi",
#     model="custom_openai/minimax-m2",
#     api_base="https://ellm.nrp-nautilus.io/v1",
#     api_key=NRP_API_KEY,
#     cache=False,
#     temperature=1.0
# )

dspy.configure(lm=lm, adapter=dspy.JSONAdapter())

# doc_dump = load_pdfs_from_directory("/home/fils/src/Projects/coffeenotes/secret/reports")
with open('990510_v1_gp17-oce_d13c_dic.csv', 'r') as file:
    doc_dump = file.read()


class DepthColumnResult(dspy.Signature):
    """Represents the min/max analysis for a single depth-related column."""
    column_name: str = dspy.OutputField(description="Name of the depth-related column")
    minvalue: float = dspy.OutputField(description="Minimum value in this column")
    maxvalue: float = dspy.OutputField(description="Maximum value in this column")
    units: str = dspy.OutputField(description="Units of measurement if determinable, otherwise 'unknown'")


class DocWriter(dspy.Signature):
    """
    You are a data scientist. Analyze this datafile and find ALL columns that have terms 
    related to depth (e.g., depth, pressure, z, level, etc.). For each depth-related column found,
    calculate the minimum and maximum values.
    """

    datafile: str = dspy.InputField()
    depth_columns: list[DepthColumnResult] = dspy.OutputField(
        description="List of all depth-related columns with their min/max values"
    )


doc_writer = dspy.RLM(
    DocWriter,
    max_iterations=10,
    sub_lm=lm,
    verbose=True
)

# Run
result = doc_writer(datafile=doc_dump)

# Write the results as JSON
output_file = Path(f"./output/depth{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

# Serialize the list of results to JSON
output_data = {
    "timestamp": datetime.datetime.now().isoformat(),
    "source_file": "990510_v1_gp17-oce_d13c_dic.csv",
    "depth_columns": [
        {
            "column_name": col.column_name,
            "minvalue": col.minvalue,
            "maxvalue": col.maxvalue,
            "units": col.units
        }
        for col in result.depth_columns
    ]
}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2)

print(f"Results written to {output_file}")
