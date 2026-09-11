#!/usr/bin/env python3
"""Render a doos_pipeline report.jsonld file as a printable PDF.

Reads JSON-LD as plain JSON. Does not import doos_pipeline or re-scan RDF.

Usage:
    python report_to_pdf.py report.jsonld
    python report_to_pdf.py report.jsonld -o /tmp/bcodmo.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#1a2332")
MUTED = colors.HexColor("#5c6773")
HEADER_BG = colors.HexColor("#1a365d")
ROW_BG = colors.HexColor("#f4f6f8")
LINE = colors.HexColor("#d0d5dd")
ACCENT = colors.HexColor("#2c5282")
PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 0.75 * inch
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
DEPTH_NAME_LIMIT = 25


def as_type_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def is_pipeline_report(doc: dict) -> bool:
    return "PipelineReport" in as_type_list(doc.get("@type")) and "PipelineReportSet" not in as_type_list(
        doc.get("@type")
    )


def is_report_set(doc: dict) -> bool:
    return "PipelineReportSet" in as_type_list(doc.get("@type"))


def format_int(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def format_bytes(value) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "—"
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f" {n / 1024:.1f} KB".strip()
    if n < 1024**3:
        return f"{n / 1024**2:.1f} MB"
    return f"{n / 1024**3:.2f} GB"


def format_pct(ratio) -> str:
    try:
        return f"{float(ratio) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def format_dt(value) -> str:
    if not value:
        return "—"
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return text


def load_report(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"Cannot read JSON-LD report {path}: {e}") from e
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not a JSON object")
    return doc


def build_styles() -> dict:
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "DoosTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=INK,
            spaceAfter=4,
            alignment=TA_LEFT,
        ),
        "subtitle": ParagraphStyle(
            "DoosSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=MUTED,
            spaceAfter=10,
        ),
        "h1": ParagraphStyle(
            "DoosH1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=ACCENT,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "DoosBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=INK,
        ),
        "note": ParagraphStyle(
            "DoosNote",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=MUTED,
            spaceAfter=6,
        ),
        "cell": ParagraphStyle(
            "DoosCell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=INK,
        ),
        "cell_right": ParagraphStyle(
            "DoosCellRight",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=INK,
            alignment=TA_RIGHT,
        ),
        "th": ParagraphStyle(
            "DoosTh",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
        ),
        "th_right": ParagraphStyle(
            "DoosThRight",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=TA_RIGHT,
        ),
        "footer": ParagraphStyle(
            "DoosFooter",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7,
            textColor=MUTED,
        ),
    }
    return styles


def P(text, style) -> Paragraph:
    return Paragraph("" if text is None else str(text), style)


def make_table(rows: list[list], col_widths: list[float], numeric_cols: set[int] | None = None) -> Table:
    numeric_cols = numeric_cols or set()
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
    ]
    for col in numeric_cols:
        commands.append(("ALIGN", (col, 1), (col, -1), "RIGHT"))
    for i in range(1, len(rows)):
        if i % 2 == 0:
            commands.append(("BACKGROUND", (0, i), (-1, i), ROW_BG))
    table.setStyle(TableStyle(commands))
    return table


def header_row(labels: list[str], styles: dict, numeric: set[int] | None = None) -> list:
    numeric = numeric or set()
    return [
        P(label, styles["th_right"] if i in numeric else styles["th"])
        for i, label in enumerate(labels)
    ]


def text_row(values: list[str], styles: dict, numeric: set[int] | None = None) -> list:
    numeric = numeric or set()
    return [
        P(value, styles["cell_right"] if i in numeric else styles["cell"])
        for i, value in enumerate(values)
    ]


def histogram_table(
    histogram: dict | None,
    styles: dict,
    *,
    label_key: str = "curie",
    limit: int | None = None,
    include_other: bool = True,
) -> list:
    buckets = list((histogram or {}).get("bucket") or [])
    if not histogram or (not buckets and not histogram.get("otherCount")):
        return [P("No histogram data.", styles["note"])]
    leftover = 0
    if limit is not None and len(buckets) > limit:
        leftover = sum(int(b.get("count") or 0) for b in buckets[limit:])
        buckets = buckets[:limit]
    other = int(histogram.get("otherCount") or 0) + leftover
    distinct = histogram.get("distinctCount")
    label_w = CONTENT_WIDTH * 0.72
    count_w = CONTENT_WIDTH * 0.28
    numeric = {1}
    rows = [header_row(["Term", "Count"], styles, numeric)]
    for bucket in buckets:
        label = bucket.get(label_key) or bucket.get("curie") or bucket.get("name") or bucket.get("@id") or "—"
        rows.append(text_row([str(label), format_int(bucket.get("count"))], styles, numeric))
    if include_other and other:
        rows.append(text_row(["(other)", format_int(other)], styles, numeric))
    flow = [make_table(rows, [label_w, count_w], numeric)]
    if distinct is not None:
        flow.append(Spacer(1, 4))
        flow.append(P(f"Distinct values: {format_int(distinct)}", styles["note"]))
    return flow


def add_page_decorations(canvas, doc, report_id: str) -> None:
    canvas.saveState()
    canvas.setFillColor(HEADER_BG)
    canvas.rect(0, PAGE_HEIGHT - 0.28 * inch, PAGE_WIDTH, 0.28 * inch, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(MARGIN, PAGE_HEIGHT - 0.18 * inch, "DOOS graph generation report")
    canvas.setFillColor(LINE)
    canvas.rect(0, 0, PAGE_WIDTH, 0.4 * inch, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    ident = report_id or ""
    if len(ident) > 90:
        ident = ident[:87] + "…"
    canvas.drawString(MARGIN, 0.18 * inch, ident)
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 0.18 * inch, f"Page {doc.page}")
    canvas.restoreState()


def story_pipeline_report(doc: dict, styles: dict) -> list:
    metrics = doc.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("PipelineReport is missing a metrics object")

    story: list = []
    story.append(P(doc.get("name") or "DOOS pipeline report", styles["title"]))
    bits = [
        f"Provider: {doc.get('provider') or '—'}",
        f"Status: {doc.get('providerStatus') or '—'}",
        f"Created: {format_dt(doc.get('dateCreated'))}",
    ]
    if doc.get("namedGraph"):
        bits.append(f"Graph: {doc['namedGraph']}")
    story.append(P("  ·  ".join(bits), styles["subtitle"]))
    if doc.get("providerDescription") or doc.get("description"):
        story.append(P(doc.get("providerDescription") or doc.get("description"), styles["body"]))
        story.append(Spacer(1, 6))

    if metrics.get("truncated"):
        story.append(
            P(
                "Scan was truncated (--max-files). Counts below describe the sampled files only.",
                styles["note"],
            )
        )

    story.append(P("Headline counts", styles["h1"]))
    headlines = [
        ("Records (schema:Dataset)", format_int(metrics.get("recordCount"))),
        ("Triples", format_int(metrics.get("tripleCount"))),
        ("Files scanned", format_int(metrics.get("fileCount"))),
        ("Size", format_bytes(metrics.get("byteCount"))),
        ("Named graphs", format_int(metrics.get("namedGraphCount"))),
        ("Parse errors", format_int(metrics.get("parseErrorCount"))),
    ]
    numeric = {1}
    rows = [header_row(["Metric", "Value"], styles, numeric)]
    for label, value in headlines:
        rows.append(text_row([label, value], styles, numeric))
    story.append(make_table(rows, [CONTENT_WIDTH * 0.45, CONTENT_WIDTH * 0.55], numeric))
    if metrics.get("sha256"):
        story.append(Spacer(1, 4))
        story.append(P(f"SHA-256: {metrics['sha256']}", styles["note"]))

    completeness = metrics.get("completeness") or {}
    story.append(P("Completeness", styles["h1"]))
    story.append(
        P(
            "Share of Dataset records with each field. Graph scan only — not a SHACL validation.",
            styles["note"],
        )
    )
    checks = [
        ("schema:name", "withName", "nameRatio"),
        ("schema:description", "withDescription", "descriptionRatio"),
        ("schema:url", "withUrl", "urlRatio"),
        ("DepBelowSurf (OIH)", "withDepBelowSurf", "depBelowSurfRatio"),
        ("Any depth variable", "withDepthVariable", "depthVariableRatio"),
        ("Depth min and max", "withDepthRange", "depthRangeRatio"),
    ]
    numeric = {1, 2}
    rows = [header_row(["Check", "Records", "Share"], styles, numeric)]
    for label, count_key, ratio_key in checks:
        rows.append(
            text_row(
                [
                    label,
                    format_int(completeness.get(count_key)),
                    format_pct(completeness.get(ratio_key)),
                ],
                styles,
                numeric,
            )
        )
    story.append(
        make_table(
            rows,
            [CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.25, CONTENT_WIDTH * 0.25],
            numeric,
        )
    )

    depth = metrics.get("depth") or {}
    story.append(P("Depth variables", styles["h1"]))
    depth_headlines = [
        ("variableMeasured links", format_int(depth.get("variableMeasuredCount"))),
        ("Depth-like PropertyValues", format_int(depth.get("depthPropertyValueCount"))),
        ("Depth with min and max", format_int(depth.get("depthWithRangeCount"))),
    ]
    numeric = {1}
    rows = [header_row(["Metric", "Value"], styles, numeric)]
    for label, value in depth_headlines:
        rows.append(text_row([label, value], styles, numeric))
    story.append(KeepTogether([make_table(rows, [CONTENT_WIDTH * 0.6, CONTENT_WIDTH * 0.4], numeric)]))
    story.append(Spacer(1, 8))
    story.append(P("Depth-like variableMeasured names", styles["note"]))
    story.extend(
        histogram_table(
            depth.get("depthNameHistogram"),
            styles,
            label_key="name",
            limit=DEPTH_NAME_LIMIT,
        )
    )

    story.append(P("RDF types", styles["h1"]))
    story.extend(histogram_table(metrics.get("typeHistogram"), styles, label_key="curie"))

    story.append(P("Predicates (top)", styles["h1"]))
    story.extend(histogram_table(metrics.get("predicateHistogram"), styles, label_key="curie"))

    story.append(P("Namespaces", styles["h1"]))
    story.extend(histogram_table(metrics.get("namespaceHistogram"), styles, label_key="curie"))

    story.append(P("Published outputs", styles["h1"]))
    dist = doc.get("distribution") or []
    if not dist:
        story.append(P("No distribution entries.", styles["note"]))
    else:
        rows = [header_row(["Name", "Format", "Exists", "SHACL"], styles, set())]
        path_rows = []
        for item in dist:
            rows.append(
                text_row(
                    [
                        item.get("name") or "—",
                        item.get("encodingFormat") or "—",
                        "yes" if item.get("exists") else "no",
                        "yes" if item.get("shaclEligible") else "no",
                    ],
                    styles,
                    set(),
                )
            )
            path_rows.append(item.get("contentUrl") or "")
        story.append(
            make_table(
                rows,
                [
                    CONTENT_WIDTH * 0.46,
                    CONTENT_WIDTH * 0.18,
                    CONTENT_WIDTH * 0.18,
                    CONTENT_WIDTH * 0.18,
                ],
            )
        )
        for url in path_rows:
            if url:
                story.append(P(url, styles["note"]))

    activity = doc.get("wasGeneratedBy") or {}
    story.append(P("Provenance", styles["h1"]))
    software = activity.get("software") or {}
    prov_rows = [
        ("Activity", activity.get("name") or "—"),
        ("Started", format_dt(activity.get("startedAtTime"))),
        ("Ended", format_dt(activity.get("endedAtTime"))),
        ("Exit code", "—" if activity.get("exitCode") is None else str(activity.get("exitCode"))),
        ("Dry run", "yes" if activity.get("dryRun") else "no"),
        (
            "Software",
            f"{software.get('name') or 'doos_pipeline'} {software.get('softwareVersion') or ''}".strip(),
        ),
    ]
    rows = [header_row(["Field", "Value"], styles)]
    for label, value in prov_rows:
        rows.append(text_row([label, value], styles))
    story.append(make_table(rows, [CONTENT_WIDTH * 0.28, CONTENT_WIDTH * 0.72]))
    steps = activity.get("steps") or []
    if steps:
        story.append(Spacer(1, 6))
        story.append(P("Commands", styles["note"]))
        for step in steps:
            cmd = step.get("command") or []
            line = " ".join(str(part) for part in cmd) if isinstance(cmd, list) else str(cmd)
            name = step.get("name") or step.get("script") or "step"
            code = step.get("returncode")
            extra = "" if code is None else f" (exit {code})"
            story.append(P(f"<b>{name}</b>{extra}: {line}", styles["body"]))
            story.append(Spacer(1, 3))

    errors = doc.get("parseError") or []
    if errors:
        story.append(P("Parse errors", styles["h1"]))
        numeric = set()
        rows = [header_row(["File", "Message"], styles)]
        for err in errors:
            rows.append(
                text_row(
                    [err.get("path") or "—", err.get("message") or "—"],
                    styles,
                )
            )
        story.append(make_table(rows, [CONTENT_WIDTH * 0.45, CONTENT_WIDTH * 0.55]))

    return story


def story_report_set(doc: dict, styles: dict) -> list:
    story: list = []
    story.append(P(doc.get("name") or "DOOS pipeline report set", styles["title"]))
    bits = [f"Created: {format_dt(doc.get('dateCreated'))}"]
    if doc.get("workDir"):
        bits.append(f"Work dir: {doc['workDir']}")
    story.append(P("  ·  ".join(bits), styles["subtitle"]))
    story.append(
        P(
            "Roll-up of per-provider PipelineReport files. Completeness ratios come from each part.",
            styles["note"],
        )
    )

    parts = doc.get("hasPart") or []
    numeric = {1, 2, 3, 4, 5}
    rows = [
        header_row(
            ["Provider", "Records", "Triples", "Files", "DepBelowSurf", "Any depth"],
            styles,
            numeric,
        )
    ]
    if not parts:
        rows.append(text_row(["(none)", "—", "—", "—", "—", "—"], styles, numeric))
    for part in parts:
        completeness = part.get("completeness") or {}
        rows.append(
            text_row(
                [
                    str(part.get("provider") or "—"),
                    format_int(part.get("recordCount")),
                    format_int(part.get("tripleCount")),
                    format_int(part.get("fileCount")),
                    format_pct(completeness.get("depBelowSurfRatio")),
                    format_pct(completeness.get("depthVariableRatio")),
                ],
                styles,
                numeric,
            )
        )
    widths = [
        CONTENT_WIDTH * 0.20,
        CONTENT_WIDTH * 0.16,
        CONTENT_WIDTH * 0.16,
        CONTENT_WIDTH * 0.12,
        CONTENT_WIDTH * 0.18,
        CONTENT_WIDTH * 0.18,
    ]
    story.append(make_table(rows, widths, numeric))
    return story


def render_pdf(doc: dict, output: Path) -> None:
    styles = build_styles()
    if is_report_set(doc):
        story = story_report_set(doc, styles)
    elif is_pipeline_report(doc):
        story = story_pipeline_report(doc, styles)
    else:
        types = ", ".join(as_type_list(doc.get("@type"))) or "(none)"
        raise ValueError(
            "Input is not a PipelineReport or PipelineReportSet "
            f"(found @type: {types})"
        )

    report_id = str(doc.get("@id") or "")
    output.parent.mkdir(parents=True, exist_ok=True)
    template = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=str(doc.get("name") or "DOOS pipeline report"),
        author="doos reportPdf",
    )
    template.build(
        story,
        onFirstPage=lambda c, d: add_page_decorations(c, d, report_id),
        onLaterPages=lambda c, d: add_page_decorations(c, d, report_id),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a doos_pipeline report.jsonld file as PDF."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to report.jsonld (PipelineReport or PipelineReportSet)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output PDF path (default: input stem with .pdf)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        if not args.input.is_file():
            raise ValueError(f"Input file not found: {args.input}")
        doc = load_report(args.input)
        output = args.output if args.output else args.input.with_suffix(".pdf")
        render_pdf(doc, output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(output)


if __name__ == "__main__":
    main()
