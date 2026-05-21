#!/usr/bin/env python3
"""Extract metadata from a NetCDF file into JSON."""

import json
import sys
from pathlib import Path
import netCDF4 as nc


def extract_metadata(nc_path: Path) -> dict:
    ds = nc.Dataset(nc_path)

    global_attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}

    dimensions = {name: len(dim) for name, dim in ds.dimensions.items()}

    variables = {}
    for name, var in ds.variables.items():
        var_attrs = {a: str(getattr(var, a)) for a in var.ncattrs()}
        variables[name] = {
            "dimensions": list(var.dimensions),
            "shape": list(var.shape),
            "dtype": str(var.dtype),
            "attributes": var_attrs,
        }

    ds.close()

    return {
        "source_file": nc_path.name,
        "global_attributes": global_attrs,
        "dimensions": dimensions,
        "variables": variables,
    }


def main():
    nc_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("33RR20220430_bottle.nc")
    out_path = nc_path.with_suffix(".metadata.json")

    metadata = extract_metadata(nc_path)

    with open(out_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Wrote metadata to {out_path}")
    print(f"  Global attributes : {len(metadata['global_attributes'])}")
    print(f"  Dimensions        : {len(metadata['dimensions'])}")
    print(f"  Variables         : {len(metadata['variables'])}")


if __name__ == "__main__":
    main()
