import pandas as pd
import duckdb

def populate_template(row):
    template = """ {{
      "@context": {{
        "@vocab": "https://schema.org/"
      }},
      "@id": "{docid}",
      "@type": "Dataset",
      "variableMeasured": [
        {{
          "@type": "PropertyValue",
          "name": "depth",
          "description": "Parsed and validated by OBIS.",
          "minValue": "{MIN}",
          "maxValue": "{MAX}",
          "propertyID": "https://obis.org/data/access/",
          "measurementTechnique": "Parsed and validated by OBIS.",
          "unitText": "m",
          "unitCode": [
            "https://qudt.org/vocab/unit/M", "https://vocab.nerc.ac.uk/collection/P06/current/ULAA/",
            "http://dbpedia.org/resource/Metre"
          ]
        }}
      ]
    }}
    """

    return template.format(MAX=row['Max(maximumDepthInMeters)'], MIN=row['Min(minimumDepthInMeters)'],
                           docid=row['docid'])


# make sure to replace 'file.parquet' with your file path
df = pd.read_parquet('idMinMaxDepth.parquet')
# df = df.head(10)

# use the values in the dataset_id to search via
# duckdb for the @id to generate the JSON-LD with.

def search_duckdb(x):
    x = duckdb.sql(f"SELECT url FROM read_json('./jsonld/obis_source/*.jsonld') WHERE url like '%{x}%'").fetchall()    # directly query a JSON file
    xs = ", ".join(str(item[0]) for item in x)
    return(xs)

df['docid'] = df['dataset_id'].apply(lambda x: search_duckdb(x))

dfe = df.explode('docid')

dfe_strict = dfe.dropna(subset=['Max(maximumDepthInMeters)', 'Min(minimumDepthInMeters)'], how='any')

dfe = dfe.assign(jsonld=dfe.apply(populate_template, axis=1))

for index, row in dfe.iterrows():
    filename = str('./jsonld/output_raw/' + row['dataset_id']) + '_depth.jsonld'  # adjust file extension as per your requirement
    with open(filename, 'w') as f:
        f.write(row['jsonld'])

dfe_strict = dfe_strict.assign(jsonld=dfe_strict.apply(populate_template, axis=1))

for index, row in dfe_strict.iterrows():
    filename = str('./jsonld/output_raw_strict/' + row['dataset_id']) + '_depth.jsonld'  # adjust file extension as per your requirement
    with open(filename, 'w') as f:
        f.write(row['jsonld'])