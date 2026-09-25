# grd-fingerprinting

This is a prototype of a stand-alone gravitational, rotational and deformational (GRD) effects fingerprinting module to be used in the FACTS2 framework. 

---

> Caution
> 🚧🚧 This is an early prototype, it will likely undergo significant changes in the near future. 🚧🚧

This module accepts GMSL projection netcdf files that carry `budget_term`/`source_region` dimensions/coordinates (see `scripts/generate_gmsl_region_files.py`). Each projection file's `source_region` is looked up directly in `data/input/grd_fingerprintmap.yml` to find its matching fingerprint netcdf (resolved against `--fingerprint-dir`); fingerprint files themselves don't need any particular coordinate/dimension to be matched against — the yml is the single source of truth for which `source_region` uses which fingerprint file.

Example GMSL netcdfs are checked in under `data/input/marimo_branch_gmsl_files`, with `source_region` values matching the region keys in `data/input/grd_fingerprintmap.yml` (e.g. `AIS.WAIS1`, `AIS.EAIS1`, `AIS.PEN`, `GIS.ALL`, `GLA.RGI01`). The fingerprint netcdfs referenced by the yml live under `data/input/FPRINT`.

```shell
uv run grd-fingerprinting --location-file ./data/input/location.lst --chunksize 50 --projection-files ./data/input/marimo_branch_gmsl_files/gmsl_ais_wais1.nc --projection-files ./data/input/marimo_branch_gmsl_files/gmsl_ais_pen.nc --grd-fingerprint-map-file ./data/input/grd_fingerprintmap.yml --fingerprint-dir ./data/input/FPRINT --output-lslr-file ./data/output/test_ais_lslr.nc --scenario ssp585 --baseyear 2005
```

For reference, here is the `xarray` repr of one of the GMSL projection files used above (`gmsl_ais_wais1.nc`):

```
<xarray.Dataset> Size: 225kB
Dimensions:           (year: 55, sample: 500, budget_term: 1, source_region: 1)
Coordinates:
  * year              (year) int64 440B 1750 1760 1770 1780 ... 2270 2280 2290
  * sample            (sample) int64 4kB 0 1 2 3 4 5 ... 494 495 496 497 498 499
  * budget_term       (budget_term) <U9 36B 'Icesheets'
  * source_region     (source_region) <U9 36B 'AIS.WAIS1'
Data variables:
    sea_level_change  (year, sample, budget_term, source_region) float64 220kB ...
Attributes:
    Conventions:  CF-1.8
    title:        Global sea level contribution from Icesheets (AIS.WAIS1)
    institution:  FACTS2
    source:       Example GMSL-step output for source=['Icesheets'], region=[...
    history:      2026-09-25T06:16:25.769424+00:00: created by generate_gmsl_...
    comment:      Synthetic example data for the FACTS2 GMSLOutput schema, wi...
    scenario:     ssp585
    baseyear:     2005
```

## Creating a GMSL projection netcdf

A GMSL projection netcdf just needs a `sea_level_change` data variable over `year`/`sample`/`budget_term`/`source_region` dimensions, where `source_region` is one of the region keys in `data/input/grd_fingerprintmap.yml`. Here's a minimal example that builds one with random values and writes it to disk:

```python
import numpy as np
import xarray as xr

years = np.arange(1750, 2291, 10)
n_samples = 500
budget_term = ["Icesheets"]
source_region = ["AIS.WAIS1"]

rng = np.random.default_rng(seed=1234)
shape = (len(years), n_samples, len(budget_term), len(source_region))
sea_level_change = rng.normal(loc=0.0, scale=50.0, size=shape)

ds = xr.Dataset(
    data_vars={
        "sea_level_change": (
            ("year", "sample", "budget_term", "source_region"),
            sea_level_change,
            {"units": "mm", "long_name": "Global mean sea level change"},
        ),
    },
    coords={
        "year": years,
        "sample": np.arange(n_samples),
        "budget_term": budget_term,
        "source_region": source_region,
    },
    attrs={"scenario": "ssp585", "baseyear": 2005},
)

ds.to_netcdf("gmsl_ais_wais1.nc")
```

See `scripts/generate_gmsl_region_files.py` for the full version of this used to generate the example files under `data/input/marimo_branch_gmsl_files`; it reads `data/input/grd_fingerprintmap.yml` directly so its `source_region` values always stay in sync with the map.

