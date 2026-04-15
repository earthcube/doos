# AODN Metadata Transformation Toolkit

## Summary

The AODN (Australian Ocean Data Network) toolkit provides a two-step XSLT pipeline for transforming ocean observation metadata into web-discoverable formats. The workflow converts ISO 19115-3:2014 XML metadata first to ISO 19139 XML, then to JSON-LD using schema.org vocabulary. This enables AODN datasets to be indexed by search engines and harvested by data aggregators, directly supporting FAIR data principles and alignment with ODIS architecture patterns.

The toolkit includes two Python scripts: one leveraging Saxon for XSLT 2.0/3.0 transformations, and another using lxml for XSLT 1.0 processing. Sample metadata and tested XSLT stylesheets are included to demonstrate the full transformation chain from source metadata to embeddable JSON-LD.

## Next Steps

- [ ] Review current XSLT mappings against latest AODN metadata profiles
- [ ] Validate JSON-LD output against schema.org Dataset requirements
- [ ] Test integration with ODIS harvest workflows
- [ ] Document any AODN-specific extensions or customizations needed
