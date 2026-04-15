# ERDDAP SDO and Croissant status

**Summary of GitHub discussion #284 and cross-references to schema.org / Croissant / JSON-LD in the ERDDAP ecosystem (as of April 2026).**

The linked discussion (https://github.com/ERDDAP/erddap/discussions/284) is titled **"Croissant files generated through ERDDAP not working with mlcroissant"** (posted ~Feb 2025 in the Q&A category by @matcor451, with replies from maintainer @ChrisJohnNOAA and others). It reports validation/runtime failures when feeding ERDDAP-generated `.croissant` JSON-LD files into the official `mlcroissant` Python library (the reference implementation for the MLCommons Croissant spec). Key pain points raised include:
- Missing or non-standard fields in the generated Croissant manifest (e.g., distribution encoding, geo extensions, or required `@context`/`@type` patterns).
- Incompatibilities with downstream AI/ML tooling that expects strict adherence to the Croissant v1 spec (which itself is built on schema.org Dataset + JSON-LD).

This is **not a new feature request**—it is a post-implementation bug report/fix discussion. ERDDAP added native Croissant schema generation in v2.28.0 (via PR #316 by @ChrisJohnNOAA) and further hardened it in v2.30.0 (PR #426, also by @ChrisJohnNOAA, addressing manifest compatibility and linking to related issue #25).

### Other ERDDAP repo / ecosystem references to schema.org, Croissant, or JSON-LD
The main `ERDDAP/erddap` repository has **very few open issues/PRs** explicitly referencing these terms because support is already baked into the core codebase (not an add-on). The pattern across references is:
- **JSON-LD + schema.org** → long-standing (pre-2020) feature for dataset discoverability (Google Dataset Search, semantic web, FAIR principles).
- **Croissant** → recent (2025) addition, explicitly schema.org/JSON-LD-based, aimed at ML-ready datasets.

Key references (main repo + closely related):
- **Core ERDDAP support (docs & releases)**: Dataset info/landing pages emit JSON-LD markup using schema.org vocabulary (e.g., `Dataset`, `variableMeasured`, `distribution`). Mentioned in FAIR data presentations and the official ERDDAP site since at least 2019. Croissant is now a first-class file type (`.croissant` endpoint) alongside `.json`, `.nc`, `.csv`, etc. It generates a Croissant-compliant manifest that includes ERDDAP metadata (CF/ACDD, variable units, geospatial bounds, etc.).
- **Discussion threads in ERDDAP/erddap**:
  - The linked #284 (Croissant + mlcroissant compatibility).
  - "Extending the Schema.org datasets descriptions for AI usecases" (another active discussion, by @thogar-computer; overlaps with Croissant because Croissant *is* a schema.org profile).
- **Releases** (v2.28.0 and v2.30.0): Explicit changelog entries for Croissant schema generation and mlcroissant compatibility fixes.
- **External but tightly coupled repos** (IOOS, CalCOFI, etc.):
  - ioos/ioos_code_lab#257: Notebook demonstrating how to harvest ERDDAP JSON-LD/schema.org markup (via `extruct` or direct `/info` page parsing).
  - ioos/catalog-ckan#208: Discusses pulling ERDDAP dataset attributes into CKAN with Schema.org output.
  - CalCOFI/workflows#24: Notes that every ERDDAP dataset already produces a JSON-LD record usable for ODIS registration.
- **Downstream / standards repos**:
  - mlcommons/croissant#791: References ERDDAP as a major data provider and discusses adding GEO type support (GeoCroissant extension) because ERDDAP gridded/tabledap datasets are heavily geospatial.

No older "pre-Croissant" issues in the main repo appear to debate *whether* to add schema.org/JSON-LD; it was implemented early and has been used in production (e.g., BCO-DMO, NOAA CoastWatch, etc.).

### Analytical take (code-agent lens: high-performance, simple code)
ERDDAP's approach is already **lean and high-performance**:
- Metadata generation is done server-side in Java (likely inside the `erddap` servlet or `gov.noaa.pfeg.coastwatch` packages) and re-uses the existing ACDD/CF attribute system—no extra database hits.
- Croissant output is just another `FileType` handler (parallel to `.json`, `.nccsv`, etc.), which keeps the code simple: one code path for all dataset types.
- JSON-LD is emitted as a lightweight `@context` + compact JSON on the `/info` and data-access pages—zero client-side processing.

**Potential simple-code improvements** (if #284 or the AI-extension discussion needs a clean fix):
1. **Make Croissant generation a thin wrapper** over the existing JSON-LD emitter (reuse the same `schema.org` vocabulary map). Avoid duplicating attribute-to-JSON logic.
2. **Add a validation hook** (post-generation) against the official Croissant JSON schema or run `mlcroissant validate` in CI—cheap static check, prevents regressions.
3. **Keep it zero-config / zero-overhead**: ERDDAP already does this efficiently; any extension should stay inside the existing `EDD` (ERDDAP Dataset) class hierarchy so griddap/tabledap users get it for free.
4. **Performance note**: Since Croissant is just metadata (not the data payload), even large datasets stay fast. No need for heavy templating—plain string/POJO → JSON is the simplest and fastest path (ERDDAP already does this for dozens of formats).

**Bottom line**: The ERDDAP team has been proactive—JSON-LD/schema.org is mature, Croissant is new but actively iterated on (v2.30 fixes address exactly the mlcroissant pain points raised in #284). The ecosystem (IOOS, mlcommons, etc.) treats ERDDAP as a *reference implementation* for these standards. If you're looking to patch or extend #284, the cleanest path is a small, targeted update inside the Croissant `FileType` handler—leverage the existing schema.org mapping and keep the diff minimal for high performance and maintainability. Let me know if you want me to sketch a concrete Java snippet or diff for the fix.
