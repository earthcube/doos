import argparse
from saxonche import PySaxonProcessor

def main():
    parser = argparse.ArgumentParser(description="Transform XML using XSLT")
    parser.add_argument("-input", "--input-file", type=str, required=True)
    parser.add_argument("-xslt", "--xslt-file", type=str, required=True)
    parser.add_argument("-output", "--output-file", type=str, required=True)
    args = parser.parse_args()

    with PySaxonProcessor(license=False) as proc:
        xslt_proc = proc.new_xslt30_processor()
        result = xslt_proc.transform_to_string(
            source_file=args.input_file,
            stylesheet_file=args.xslt_file
        )
        with open(args.output_file, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Transformation complete. Output written to {args.output_file}")

if __name__ == "__main__":
    main()