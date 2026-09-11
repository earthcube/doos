# reportPdf

Render a `doos_pipeline` **`report.jsonld`** file as a printable PDF.

This directory is a **consumer only**. It does not run providers, does not
import `src/doos_pipeline`, and does not re-scan RDF. The JSON-LD file is the
whole input.

## Setup

```bash
uv pip install -r scripts/reportPdf/requirements.txt
```

`reportlab` is the only extra dependency.

## Usage

```bash
python scripts/reportPdf/report_to_pdf.py runs/doos_pipeline/<utc>/report.jsonld
python scripts/reportPdf/report_to_pdf.py report.jsonld -o /tmp/bcodmo.pdf
python scripts/reportPdf/report_to_pdf.py --help
```

Default output is the input path with a `.pdf` suffix.

Produces a `PipelineReport` (full metrics) or a `PipelineReportSet` (provider
roll-up table) depending on `@type` in the JSON-LD.

## What the PDF contains

For a single-provider report: headline counts, completeness (name / description /
url / `DepBelowSurf` / depth range), depth-name histogram, RDF type / predicate /
namespace tables, published outputs, and PROV activity (commands, times).

Charts and a web dashboard are out of scope here.
