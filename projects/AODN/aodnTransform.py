import lxml.etree as ET
import argparse

def main():
    parser = argparse.ArgumentParser(description="Transform XML using XSLT to JSON-LD schema.org vocab")
    parser.add_argument(
        "-xml", "--xml-file",
        type=str,
        required=True,
        help="Path to the XML file to transform"
    )
    parser.add_argument(
        "-xslt", "--xslt-file",
        type=str,
        required=True,
        help="Path to the XSLT file for transformation"
    )
    args = parser.parse_args()

    dom = ET.parse(args.xml_file)
    xslt = ET.parse(args.xslt_file)  ## convert to JSON-LD schema.org voc
    transform = ET.XSLT(xslt)
    newdom = transform(dom)

    print(newdom)


if __name__ == "__main__":
    main()