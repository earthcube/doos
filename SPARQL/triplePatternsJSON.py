import csv
import argparse
import json

def get_var_name(url):
    """Creates a variable name from a URL."""
    if not url:
        return ""
    if '#' in url:
        name = url.split('#')[-1]
    else:
        name = url.split('/')[-1]
    # Handle potential empty strings from trailing slashes
    if not name and len(url.split('/')) > 1:
        name = url.split('/')[-2]
    return name.lower()

def process_csv(file_path):
    """Processes the CSV file and prints SPARQL patterns as JSON."""
    results = []
    with open(file_path, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header row
        for row in reader:
            used_vars = set()
            pattern_triples = []
            description = ""

            level = int(row[0])
            top_type = row[1]

            if level == 0:
                prop = row[2]
                var_name = get_var_name(prop)
                pattern_triples.append(f"?{get_var_name(top_type)} <{prop}> ?{var_name}")

                prop_name = get_var_name(prop)
                top_type_name = get_var_name(top_type)
                description = f"Triple pattern to get the '{prop_name}' from a '{top_type_name}'."

            else:
                subject_var = f"?{get_var_name(top_type)}"
                used_vars.add(subject_var)
                prop_names = []

                for i in range(level):
                    prop_index = 2 + (i * 2)
                    type_index = 3 + (i * 2)

                    prop = row[prop_index]
                    obj_type = row[type_index]

                    if not prop:
                        continue

                    prop_names.append(f"'{get_var_name(prop)}'")

                    # Determine base name for the object variable
                    if obj_type:
                        base_var_name = f"{get_var_name(prop)}_{get_var_name(obj_type)}"
                    else:
                        base_var_name = get_var_name(prop)

                    # Check for uniqueness and append a counter if needed
                    object_var = f"?{base_var_name}"
                    count = 2
                    while object_var in used_vars:
                        object_var = f"?{base_var_name}_{count}"
                        count += 1

                    pattern_triples.append(f"{subject_var} <{prop}> {object_var}")

                    # The new object becomes the subject for the next triple
                    subject_var = object_var
                    used_vars.add(object_var)

                top_type_name = get_var_name(top_type)
                description = f"Triple pattern for a path from a '{top_type_name}' through {', '.join(prop_names)}."

            if pattern_triples:
                results.append({
                    "pattern": pattern_triples,
                    "description": description
                })

    print(json.dumps(results, indent=4))

def main():
    parser = argparse.ArgumentParser(description='Process a CSV file to generate JSON with SPARQL patterns.')
    parser.add_argument('input_file', type=str, help='The path to the input CSV file.')
    args = parser.parse_args()
    process_csv(args.input_file)

if __name__ == "__main__":
    main()
