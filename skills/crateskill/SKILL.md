---
name: url-to-rocrate
description: >
  Download a file from a URL and package it as an Attached RO-Crate (1.2).
  Use when the user wants to create an RO-Crate, Research Object Crate, or
  ro-crate-metadata.json from a file URL. Triggers on "ro-crate", "RO-Crate",
  "download and crate", "url to ro-crate", or "/url-to-rocrate".
metadata:
  spec: "https://w3id.org/ro/crate/1.2"
  version: "1.0"
---

# URL to RO-Crate

Download a file from a **URL** and create a minimal **Attached RO-Crate Package**
conforming to [RO-Crate 1.2](https://www.researchobject.org/ro-crate/specification/1.2/).

## What it does

`assets/make_rocrate.py`:

1. **Downloads** the file at the given URL (User-Agent, 30 s timeout, follows redirects).
2. **Writes** an Attached RO-Crate directory:
   ```
   <out-dir>/
   |   ro-crate-metadata.json
   |   <downloaded-file>
   ```
3. **Emits** `ro-crate-metadata.json` with the required RO-Crate 1.2 graph:
   - **RO-Crate Metadata Descriptor** (`CreativeWork`, `about` → root)
   - **Root Data Entity** (`Dataset` with `name`, `description`, `datePublished`, `license`, `hasPart`)
   - **File Data Entity** (`File` with `contentSize`, `encodingFormat`, `contentUrl`, `sdDatePublished`)
   - **License** contextual entity
   - **CreateAction** provenance for the download

## Run it

```bash
python assets/make_rocrate.py <file-url> [--out-dir DIR] [--name NAME] [--description TEXT] [--license URI]
```

Example:

```bash
python assets/make_rocrate.py https://example.org/data/survey.csv \
  --out-dir ./my-crate \
  --name "Survey responses" \
  --description "CSV downloaded from example.org"
```

The script prints a JSON summary with `crate_dir`, `metadata_file`, `data_file`, and file metadata.

## Inputs

| Input | Required | Notes |
|-------|----------|-------|
| `url` | yes | Direct download URL (not a landing page) |
| `--out-dir` | no | Defaults to `./ro-crate-output` |
| `--name` | no | Root `Dataset` name; defaults to filename |
| `--description` | no | Root `Dataset` description |
| `--license` | no | Defaults to CC0 1.0 |

## RO-Crate layout

The output is an **Attached RO-Crate Package** per the spec:

- `ro-crate-metadata.json` sits in the RO-Crate root.
- The downloaded file is the payload; its `@id` in metadata matches the relative path.
- `@context` is `https://w3id.org/ro/crate/1.2/context`.
- Root `@id` is `./`.

## Agent workflow

When invoked with a URL:

1. Confirm the URL points to a **directly downloadable file** (not an HTML landing page).
2. Run `assets/make_rocrate.py` with the URL and any user-supplied name/description.
3. Report the output directory and show the generated `ro-crate-metadata.json`.
4. If the user provides a license other than CC0, pass `--license <URI>`.

## Limitations

- Single-file crates only (one download per invocation).
- License defaults to CC0; override with `--license` when the source license is known.
- Filename is taken from `Content-Disposition` or the URL path; falls back to `download`.