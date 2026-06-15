import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON

def sparql_to_dataframe(endpoint: str, query: str) -> pd.DataFrame:
    """
    Execute a SPARQL query against an endpoint and return results as a DataFrame.

    Args:
        endpoint: SPARQL endpoint URL
        query: SPARQL query string

    Returns:
        DataFrame with SPARQL variables as column headers
    """
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)

    results = sparql.query().convert()

    columns = results["head"]["vars"]
    rows = []

    for binding in results["results"]["bindings"]:
        row = {var: binding.get(var, {}).get("value", None) for var in columns}
        rows.append(row)

    return pd.DataFrame(rows, columns=columns)


# Load SPARQL query from file and execute
with open('../SPARQL/yl1.rq', 'r') as f:
    query = f.read()

endpoint = 'https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans'
df = sparql_to_dataframe(endpoint, query)
print(df)
