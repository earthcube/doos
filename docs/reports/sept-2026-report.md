# DOOS Activity Report — May & June 2026

**Repository:** [earthcube/doos](https://github.com/earthcubeprojects/doos)  
**Reporting period:** September 2026  
**Author:** Douglas Fils  
**Generated:** 11 September 2026

---

It seems to me there are a few productds we are working toward.

1) Guidance on using the DOOS profile in depth to express depth in classic SOSO based metadata
  * along with this is conversion to/from the GeoCroissant profile and leveraging that with the ERDDAP community to get metadata expressing depth
  * Working with the [revised ODIS efforts](https://search-demo.odis.org/) to get depth into the workflow there.  Goal, make the results of this work into a product that ODIS can directly ingest.  These means "DOOS" needs to become a working repo that generates products for both DeCODER and ODIS Search. 
    * Approaching ways to leverage depth that is in the data but not the UI [https://odis.provisium.io/?q=coral&types=Dataset](https://odis.provisium.io/?q=coral&types=Dataset)
  * shared validations
2)
3) A stretch goal is to express these in a manner than can be used my a set of skills or a harness setup (ala loom)
  * Or, provide a means for code / notebook generation


* We are working toward a transformation of the DOOS repo into a sort of data workflow that centers on the creation of metadata products from the project sources.  The product is the depth enriched metadata that can be used by ODIS and DeCODER.   We will want to then express multiple elements to make this approach more scalable:

  * profile details in SOSO (for now)
  * mapping to other profiles (GeoCroissant for example)
  * SHACL validation
  * SHACL rules (no examples here yet)

* Fixes for the AODN XLST to address bad characters in the license and description.  Add approach that address this issue in general


Review:

[../../SHACL/vertical_coord_aliases.md](depth coordinates review)
