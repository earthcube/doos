import geopandas as gpd
import sys
import argparse
import morph_kgc
import pandas as pd
import os
import json
from pyld import jsonld
from rdflib import Graph

def print_info(parquet_file):
    gdf = pd.read_parquet(parquet_file)

    # Print len
    print("Length:", len(gdf))

    # Print all columns
    print("Columns:", list(gdf.columns))

    # Select some columns to test with
    selected_cols = ['themes', 'id', 'title', 'depth_max_in_meters', 'description', 'geometry', 'mission', 'themes']
    if all(col in gdf.columns for col in selected_cols):
        subset_gdf = gdf[selected_cols]
        print(subset_gdf.head(10))
    else:
        missing = [col for col in selected_cols if col not in gdf.columns]
        print(f"One or more columns not found: {missing}. Full columns: {list(gdf.columns)}")

    ## TODO add in the elements to convert the dataframe to RDF via RML

def tocsv(parquet_file, csv_output="output.csv"):
    # Read the GeoParquet file (use read_parquet for specificity)
    gdf = gpd.read_parquet(parquet_file)

    # Convert the GeoDataFrame to a regular DataFrame, ensuring the geometry is in WKT format
    gdf['geometry'] = gdf.geometry.to_wkt()

    # Write the DataFrame to a CSV file
    try:
        gdf.to_csv(csv_output, index=False)
        print(f"CSV exported to {csv_output}")
    except Exception as e:
        print(f"Error writing CSV: {e}")

def rml_mapping(parquet_file, template):
    gdf = gpd.read_parquet(parquet_file)

    # Convert geometry to WKT strings for RML compatibility
    gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.wkt if geom else '')

    selected_cols = ['id', 'title', 'depth_max_in_meters', 'description', 'geometry', 'mission', 'themes']
    if all(col in gdf.columns for col in selected_cols):
        df = gdf[selected_cols]

        # Create an output directory if it doesn't exist
        output_dir = "data/output"
        os.makedirs(output_dir, exist_ok=True)

        # Read JSON-LD template from a file
        template_file = "./template/argo1.json"  # You can change this path as needed
        with open(template_file, 'r', encoding='utf-8') as f:
            json_ld_template = json.load(f)


        for index, row in df.iterrows():
            # Create a copy of the template
            json_ld_doc = json.loads(json.dumps(json_ld_template))

            # set the relation URI between the graphs
            # /geosparql:hasGeometry/geosparql:asWKT/@value
            json_ld_doc["name"] = row['id']
            json_ld_doc["title"] = row['title']
            json_ld_doc["description"] = row['description']
            json_ld_doc["variableMeasured"][0]["maxValue"] = row['depth_max_in_meters']
            json_ld_doc["geosparql:hasGeometry"]["geosparql:asWKT"]["@value"] = row['geometry']

            # --------------------------------------------
            # Convert JSON-LD to N-Quads
            nquads = jsonld.to_rdf(json_ld_doc, {'format': 'application/n-quads'})

            # Parse with rdflib and skolemize blank nodes
            g = Graph()
            g.parse(data=nquads, format='nquads')
            g = g.skolemize()  # Replace blank nodes with skolem IRIs

            # Serialize to N-Triples
            ntriples = g.serialize(format='nt')

            # Create filename using the run_accession
            filename = f"{row['id']}.nt"
            filepath = os.path.join(output_dir, filename)

            # Write the N-Triples file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(ntriples)

            print(f"Created: {filepath}")


        return None
    return None

def rml_mapping_parquet(parquet_file, template):
    gdf = pd.read_parquet(parquet_file)

    selected_cols = ['title']
    if all(col in gdf.columns for col in selected_cols):
        df0 = gdf[selected_cols]

        # Convert geometry to WKT strings for RML compatibility
        # gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.wkt if geom else '')
        # df = pd.DataFrame(gdf2)

        df = df0.apply(lambda x: x.astype(str))
        print(df.columns)
        print(df.head(10))
        dfh = df.head(10)

        data_dict = {"variable1": df0}

        config = f"""
            [DataSource]
            mappings={template}
            output_format=nt
            number_of_processes=1
        """

        g_rdflib = morph_kgc.materialize(config, data_dict)

        # Ensure we get text N-Triples serialization
        nt = g_rdflib.serialize(format="nt")
        if isinstance(nt, bytes):  # depending on rdflib version
            nt = nt.decode("utf-8")
        return nt
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Geoparquet processing tool")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # 'info' subcommand
    info_parser = subparsers.add_parser("info", help="Print parquet file info")
    info_parser.add_argument("-parquet", required=True, help="Path to the parquet file")

    # 'tocsv' subcommand
    tocsv_parser = subparsers.add_parser("tocsv", help="Convert parquet to csv")
    tocsv_parser.add_argument("-parquet", required=True, help="Path to the parquet file")

    # 'rml' subcommand
    rml_parser = subparsers.add_parser("rml", help="Run RML mapping")
    rml_parser.add_argument("-parquet", required=True, help="Path to the parquet file")
    rml_parser.add_argument("-mapping", required=True, help="Path to the mapping template file")

    args = parser.parse_args()

    if args.command == "info":
        print_info(getattr(args, "parquet"))
    elif args.command == "tocsv":
        tocsv(getattr(args, "parquet"))
    elif args.command == "rml":
        result = rml_mapping(getattr(args, "parquet"), getattr(args, "mapping"))
        print("RDF output:")
        print(result)
