# AODN

## About

This directory contains tools for transforming AODN (Australian Ocean Data Network) metadata records between ISO formats and to JSON-LD schema.org vocabulary using XSLT stylesheets.

---

> **Note:** This script requires `saxonche`. Install it with:
> ```bash
> uv add saxonche
> ```

---

## When to Use Which Script

| Scenario | Script |
|----------|--------|
| Quick stdout preview, XSLT 1.0 stylesheet | `aodnTransform.py` |
| Write output to file, XSLT 2.0/3.0 stylesheet (e.g. `toISO19139.xsl`) | `convert_script.py` |