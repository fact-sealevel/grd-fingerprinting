# grd-fingerprinting

This is a prototype of a stand-alone gravitational, rotational and deformational (GRD) effects fingerprinting module to be used in the FACTS2 framework. 

---

> Caution
> 🚧🚧 This is an early prototype, it will likely undergo significant changes in the near future. 🚧🚧

> [!NOTE]
> Currently, the only module with a working prototype for providing GMSL inputs to grd-fingerprinting is [ipccar5](https://github.com/fact-sealevel/ipccar5/tree/wire_in_grd) (`wire_in_grd` branch). Prototypes for additional modules will be released soon.
>
> To connect your own GMSL module, see [Wiring a GMSL module to grd-fingerprinting](wiring_a_gmsl_module.md), which walks through running ipccar5 and grd-fingerprinting locally and what your module's outputs need to look like.

## What it does

grd-fingerprinting turns global mean sea-level (GMSL) projections into local sea-level projections at a list of locations. In each run it:

1. reads the GMSL projection files you pass with `--projection-files`;
2. looks up each file's `source_region` in a fingerprint map yaml (`--grd-fingerprint-map-file`) to find the fingerprint netcdf for that region (resolved against `--fingerprint-dir`);
3. scales each source region's projection by its fingerprint at every location in `--location-file`;
4. **adds together all the source regions passed in the run** and writes the total to a single output file (`--output-lslr-file`).

## Choosing what to localize

Because a run adds together every source region it is given, the projection files you pass decide what the output represents. Pass one region to get that region's local contribution, or several to get their combined contribution. For example, with ipccar5 outputs:

| Output you want | Projection files to pass |
|---|---|
| Local WAIS | `wais_gslr.nc` |
| Local EAIS | `eais_gslr.nc` |
| Local AIS (WAIS + EAIS) | `wais_gslr.nc` and `eais_gslr.nc` |
| Local GIS | `gis_gslr.nc` |
| Local glaciers (all 18 RGI regions) | `glaciers_regions_gslr.nc` |

To get several of these (e.g. WAIS and EAIS separately), run grd-fingerprinting once for each, with a different `--output-lslr-file`.

Two rules apply to every run:

- **One budget term per run.** All projection files in a run must have the same `budget_term` (e.g. all `icesheets`, or all `glaciers`). grd-fingerprinting stops with an error if they don't. Run it separately for each budget term.
- **Don't pass a total together with its parts.** For example, ipccar5's `ais_gslr.nc` is WAIS + EAIS, so passing it with `wais_gslr.nc` and `eais_gslr.nc` would count Antarctica twice. The ipccar5 fingerprint map has no `ais` entry, so passing `ais_gslr.nc` raises an error.

## Running it

| Option | Description |
|---|---|
| `--projection-files` | A GMSL projection netcdf; repeat the option for each file |
| `--grd-fingerprint-map-file` | yaml mapping each `source_region` to a fingerprint file |
| `--fingerprint-dir` | Directory holding the fingerprint netcdfs named in the map |
| `--location-file` | Tab-separated file of `name`, `id`, `lat`, `lon`, one location per line |
| `--chunksize` | Number of locations to process at a time (pass a value; leaving it out currently causes an error) |
| `--scenario` | Emissions scenario, written to the output metadata |
| `--baseyear` | Base year of the projections, written to the output metadata |
| `--output-lslr-file` | Path of the local projection file to write |

For ipccar5, the map is `data/input/mappings/ipccar5_fingerprintmap.yml` and the fingerprint netcdfs it references live under `data/input/fingerprint/ipccar5`.

### Example

Generate GMSL projections with ipccar5 (see the [ipccar5 `wire_in_grd` branch](https://github.com/fact-sealevel/ipccar5/tree/wire_in_grd)), then localize them. This run passes the WAIS and EAIS projections, so the output is local AIS:

```shell
uv run grd-fingerprinting \
  --projection-files ../ipccar5/data/output/wais_gslr.nc \
  --projection-files ../ipccar5/data/output/eais_gslr.nc \
  --grd-fingerprint-map-file ./data/input/mappings/ipccar5_fingerprintmap.yml \
  --fingerprint-dir ./data/input/fingerprint/ipccar5 \
  --location-file ./data/input/location.lst \
  --chunksize 50 \
  --scenario ssp585 \
  --baseyear 2005 \
  --output-lslr-file ./data/output/ais_lslr.nc
```

For local WAIS only, pass just `wais_gslr.nc` and change the output to e.g. `./data/output/wais_lslr.nc`.

grd-fingerprinting prints the fingerprint it selected for each source region, e.g. `wais: icesheets -> ./data/input/fingerprint/ipccar5/fprint_wais.nc`, which is a quick way to check the right fingerprints were used.

The output file holds `sea_level_change` (mm) with dimensions `(samples, years, locations)`, plus each location's `lat` and `lon`, and records the run's `budget_term`, `scenario` and `baseyear` as attributes.

## GMSL projection files

A GMSL projection netcdf needs a `sea_level_change` data variable over `sample`/`year`/`budget_term`/`source_region` dimensions (in any order), where each `source_region` is a key in the fingerprint map. A file can hold one source region or several. For reference, here is the `xarray` repr of `wais_gslr.nc` from the example above:

```
<xarray.Dataset> Size: 60kB
Dimensions:           (sample: 500, year: 14, budget_term: 1, source_region: 1)
Coordinates:
  * sample            (sample) int64 4kB 0 1 2 3 4 5 ... 494 495 496 497 498 499
  * year              (year) int64 112B 2020 2030 2040 2050 ... 2130 2140 2150
  * budget_term       (budget_term) <U9 36B 'icesheets'
  * source_region     (source_region) <U4 16B 'wais'
Data variables:
    sea_level_change  (sample, year, budget_term, source_region) float64 56kB ...
Attributes:
    Conventions:  CF-1.11
    title:        Global mean sea-level contribution from WAIS using the ice ...
    source:       FACTS2 ipccar5 0.1.3
    history:      2026-10-16T22:42:20Z: created by FACTS2 pipeline icesheets-...
    baseyear:     2005
    scenario:     ssp585
```

For an example of a GMSL module writing outputs in this structure, see `make_gmsl_ds` and `write_gmsl_projection` in ipccar5's [`io.py`](https://github.com/fact-sealevel/ipccar5/blob/wire_in_grd/src/ipccar5/io.py) on the `wire_in_grd` branch. It writes one file per source region (e.g. `gis`, `wais`, `eais`) as well as a single file with a multi-valued `source_region` dimension (one entry per glacier region). Its `source_region` values are the keys in `data/input/mappings/ipccar5_fingerprintmap.yml`.

To connect your own module, see [wiring_a_gmsl_module.md](wiring_a_gmsl_module.md).
