import argparse
import json
import sys
from pathlib import Path

import lxml.etree as ET


def main():
    parser = argparse.ArgumentParser(
        description="Transform XML using XSLT to JSON-LD schema.org vocab"
    )
    parser.add_argument(
        "-xml",
        "--xml-file",
        type=str,
        required=True,
        help="Path to the XML file to transform",
    )
    parser.add_argument(
        "-xslt",
        "--xslt-file",
        type=str,
        required=True,
        help="Path to the XSLT file for transformation",
    )
    parser.add_argument(
        "-output",
        "--output-file",
        type=str,
        default=None,
        help="Optional output JSON-LD file (default: stdout)",
    )
    args = parser.parse_args()

    xml_path = Path(args.xml_file)
    xslt_path = Path(args.xslt_file)

    for label, path in (("XML", xml_path), ("XSLT", xslt_path)):
        if not path.is_file():
            print(f"Error: {label} file not found: {path}", file=sys.stderr)
            sys.exit(1)

    try:
        dom = ET.parse(str(xml_path))
        xslt = ET.parse(str(xslt_path))
        transform = ET.XSLT(xslt)
        result = transform(dom)
        if not result:
            print("Error: XSLT transformation produced no output", file=sys.stderr)
            sys.exit(1)

        output_text = str(result)
        if args.output_file:
            out_path = Path(args.output_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output_text, encoding="utf-8")
            json.loads(output_text)
            print(f"Transformation complete. Output written to {out_path}")
        else:
            print(output_text)
    except json.JSONDecodeError as e:
        print(f"Error: transformation output is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()