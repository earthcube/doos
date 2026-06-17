import csv
import argparse


def get_var_name(url):
    """Creates a variable name from a URL."""
    if not url:
        return ""
    if "#" in url:
        name = url.split("#")[-1]
    else:
        name = url.split("/")[-1]
    # Handle potential empty strings from trailing slashes
    if not name and len(url.split("/")) > 1:
        name = url.split("/")[-2]
    return name.lower()


def process_csv(file_path):
    """Processes the CSV file and prints SPARQL patterns."""
    with open(file_path, "r") as f:
        reader = csv.reader(f)
        next(reader)  # Skip header row
        for row in reader:
            used_vars = set()

            level = int(row[0])
            top_type = row[1]

            if level == 0:
                prop = row[2]
                var_name = get_var_name(prop)
                print(f"?{get_var_name(top_type)} <{prop}> ?{var_name}")
            else:
                subject_var = f"?{get_var_name(top_type)}"
                used_vars.add(subject_var)

                for i in range(level):
                    prop_index = 2 + (i * 2)
                    type_index = 3 + (i * 2)

                    prop = row[prop_index]
                    obj_type = row[type_index]

                    if not prop:
                        continue

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

                    print(f"{subject_var} <{prop}> {object_var}")

                    # The new object becomes the subject for the next triple
                    subject_var = object_var
                    used_vars.add(object_var)

            print()  # Add blank line after each row's output


def main():
    parser = argparse.ArgumentParser(
        description="Process a CSV file to generate SPARQL patterns."
    )
    parser.add_argument("input_file", type=str, help="The path to the input CSV file.")
    args = parser.parse_args()
    process_csv(args.input_file)


if __name__ == "__main__":
    main()
