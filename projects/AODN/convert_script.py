import argparse
import sys
from pathlib import Path

from saxonche import PySaxonProcessor


def main():
    parser = argparse.ArgumentParser(description="Transform XML using XSLT")
    parser.add_argument("-input", "--input-file", type=str, required=True)
    parser.add_argument("-xslt", "--xslt-file", type=str, required=True)
    parser.add_argument("-output", "--output-file", type=str, required=True)
    args = parser.parse_args()

    input_path = Path(args.input_file)
    xslt_path = Path(args.xslt_file)
    output_path = Path(args.output_file)

    for label, path in (("Input", input_path), ("XSLT", xslt_path)):
        if not path.is_file():
            print(f"Error: {label} file not found: {path}", file=sys.stderr)
            sys.exit(1)

    try:
        with PySaxonProcessor(license=False) as proc:
            xslt_proc = proc.new_xslt30_processor()
            result = xslt_proc.transform_to_string(
                source_file=str(input_path),
                stylesheet_file=str(xslt_path),
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result, encoding="utf-8")
        print(f"Transformation complete. Output written to {output_path}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()