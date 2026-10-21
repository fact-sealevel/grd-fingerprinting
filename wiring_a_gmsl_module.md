# Wiring a GMSL module to grd-fingerprinting

This guide is for developers of a FACTS2 module that produces global mean sea-level
(GMSL) projections and want `grd-fingerprinting` to turn them into local sea-level
projections.

The split of responsibilities is:

- **Your module** writes global projections only, one netCDF per source region (or one
  netCDF with several source regions), labelled with a `budget_term` and `source_region`.
- **grd-fingerprinting** looks up each `source_region` in a fingerprint map, applies the
  matching fingerprint at each location, sums all source regions in the budget term, and
  writes the local projections.

The reference implementation is **ipccar5** on its
[`wire_in_grd` branch](https://github.com/fact-sealevel/ipccar5/tree/wire_in_grd). It is
currently the only module wired this way. Part 1 runs it end to end on your machine;
Part 2 describes what your module needs to do the same.

## What grd-fingerprinting expects

Each projection file passed with `--projection-files` must have:

| Item | Requirement |
|---|---|
| Data variable | `sea_level_change`, units `mm` |
| Dimensions | `sample`, `year`, `budget_term`, `source_region` (any order) |
| `budget_term` | A dimension (length 1 is fine), e.g. `"glaciers"`, `"icesheets"` |
| `source_region` | A dimension; every value must be a key in the fingerprint map |
| `year`, `sample` | The same values in every file passed in one run |

And for each run:

- **One budget term per run.** grd sums every source region within a budget term into a
  single output file, and stops with an error if the inputs contain more than one
  budget term. Run it once per budget term.
- **No overlapping regions.** Don't pass a total together with its parts (ipccar5's `ais`
  is `wais + eais`, so passing all three would count Antarctica twice).
- `--scenario` and `--baseyear` are passed on the command line; grd does not read them
  from the files.

## Part 1: run the ipccar5 reference locally

### 1. Clone both repos side by side

```shell
mkdir facts2 && cd facts2
git clone -b wire_in_grd https://github.com/fact-sealevel/ipccar5.git
git clone -b marimo_version https://github.com/fact-sealevel/grd-fingerprinting.git
```

### 2. Get the input data

`data/` is gitignored in both repos, so the inputs need to be downloaded.

**ipccar5** needs the glacier and ice sheet fraction files (from Zenodo) and a FaIR
temperature file:

```shell
cd ipccar5
mkdir -p data/input data/output
curl -sL https://zenodo.org/record/7478192/files/ipccar5_glaciers_project_data.tgz | tar -zx -C ./data/input
curl -sL https://zenodo.org/record/7478192/files/ipccar5_icesheets_project_data.tgz | tar -zx -C ./data/input
cd ..
```

The FaIR file is the climate output of the
[fair-temperature](https://github.com/fact-sealevel/fair-temperature) module. Generate it
with the fair-temperature container (this needs Docker), from `facts2/`:

```shell
mkdir -p fair/data/input fair/data/output
curl -sL https://zenodo.org/record/7478192/files/fair_temperature_fit_data.tgz | tar -zx -C ./fair/data/input
curl -sL https://zenodo.org/record/7478192/files/fair_temperature_preprocess_data.tgz | tar -zx -C ./fair/data/input

docker run --rm \
  -v ./fair/data:/data \
  ghcr.io/fact-sealevel/fair-temperature:0.2.1 \
  --pipeline-id=fair-ssp585 \
  --scenario=ssp585 \
  --nsamps=500 \
  --seed=1234 \
  --output-climate-file=/data/output/climate.nc \
  --output-gsat-file=/data/output/gsat.nc \
  --output-oceantemp-file=/data/output/oceantemp.nc \
  --output-ohc-file=/data/output/ohc.nc \
  --rcmip-file=/data/input/rcmip/rcmip-emissions-annual-means-v5-1-0.csv \
  --param-file=/data/input/parameters/fair_ar6_climate_params_v4.0.nc

cp fair/data/output/climate.nc ipccar5/data/input/climate.nc
```

- `--nsamps` defaults to 10 in fair-temperature; set it to the number of samples you want
  ipccar5 to use (500 below).
- `--scenario` must match the `--scenario` passed to ipccar5; ipccar5 stops with an
  error if the climate file is for a different scenario.
- Only `climate.nc` is used by ipccar5; the other three outputs are required by the
  fair-temperature CLI.

fair-temperature 0.2.1 stores `surface_temperature` in a group named after the scenario,
with dimensions `(years, samples)`. ipccar5 reads that layout as well as a flat file with
`surface_temperature(year, sample)` at the root.

**grd-fingerprinting** needs the fingerprints used by ipccar5, the ipccar5 fingerprint
map, and a location file:

```shell
cd grd-fingerprinting
mkdir -p data/input/fingerprint/ipccar5 data/input/mappings data/output
curl -sL https://zenodo.org/record/7478192/files/grd_fingerprints_data.tgz \
  | tar -zx -C ./data/input/fingerprint/ipccar5 --strip-components=1 FPRINT
printf "New_York\t12\t40.70\t-74.01\n" > data/input/location.lst
cd ..
```

Then save the map in the [appendix](#appendix-ipccar5-fingerprint-map) as
`grd-fingerprinting/data/input/mappings/ipccar5_fingerprintmap.yml`.

### 3. Write global projections with ipccar5

From `ipccar5/`. `--nsamps` should equal the number of samples in the FaIR file (500 here).

```shell
cd ipccar5

uv run ipccar5 glaciers \
  --scenario ssp585 \
  --nsamps 500 \
  --climate-data-file data/input/climate.nc \
  --glacier-fraction-file data/input/glacier_fraction.txt \
  --global-output-file data/output/glaciers_gslr.nc \
  --global-regions-output-file data/output/glaciers_regions_gslr.nc

uv run ipccar5 icesheets \
  --scenario ssp585 \
  --nsamps 500 \
  --climate-data-file data/input/climate.nc \
  --icesheet-fraction-file data/input/icesheet_fraction.txt \
  --global-gis-output-file data/output/gis_gslr.nc \
  --global-ais-output-file data/output/ais_gslr.nc \
  --global-wais-output-file data/output/wais_gslr.nc \
  --global-eais-output-file data/output/eais_gslr.nc

cd ..
```

`glaciers_gslr.nc` is the global glacier total (`source_region = "global"`) and
`glaciers_regions_gslr.nc` holds the same projection split into 18 RGI regions
(`source_region = rgi01 … rgi18`). Only the regions file is passed to grd.

### 4. Localize with grd-fingerprinting

From `grd-fingerprinting/`, once per budget term:

```shell
cd grd-fingerprinting

# Glaciers: the 18 RGI regions
uv run grd-fingerprinting \
  --projection-files ../ipccar5/data/output/glaciers_regions_gslr.nc \
  --grd-fingerprint-map-file ./data/input/mappings/ipccar5_fingerprintmap.yml \
  --fingerprint-dir ./data/input/fingerprint/ipccar5 \
  --location-file ./data/input/location.lst \
  --chunksize 50 --scenario ssp585 --baseyear 2005 \
  --output-lslr-file ./data/output/glaciers_lslr.nc

# Ice sheets: GIS, WAIS and EAIS (not AIS, which is WAIS + EAIS)
uv run grd-fingerprinting \
  --projection-files ../ipccar5/data/output/gis_gslr.nc \
  --projection-files ../ipccar5/data/output/wais_gslr.nc \
  --projection-files ../ipccar5/data/output/eais_gslr.nc \
  --grd-fingerprint-map-file ./data/input/mappings/ipccar5_fingerprintmap.yml \
  --fingerprint-dir ./data/input/fingerprint/ipccar5 \
  --location-file ./data/input/location.lst \
  --chunksize 50 --scenario ssp585 --baseyear 2005 \
  --output-lslr-file ./data/output/icesheets_lslr.nc
```

grd prints one line per source region showing the fingerprint it selected, e.g.
`wais: icesheets -> ./data/input/fingerprint/ipccar5/fprint_wais.nc`. Every source region
in your inputs should appear with the fingerprint you intended.

## Part 2: wire your own module

### 1. Write outputs in the expected structure

Use the same, or similar, functions as ipccar5's
[`io.py`](https://github.com/fact-sealevel/ipccar5/blob/wire_in_grd/src/ipccar5/io.py):

- **`make_gmsl_ds(...)`** builds the dataset. Pass a single `source_region` string with
  samples shaped `[sample, year]`, or a list of source regions with samples shaped
  `[sample, year, region]`. It always adds `budget_term` and `source_region` as
  dimensions, names the variable `sea_level_change` (the `GMSL_VARIABLE` constant), and
  sets CF-style attributes (`Conventions`, `title`, `source`, `history`, `baseyear`,
  `scenario`). An optional `region_names` list is stored as a `region_names` attribute
  on `source_region`.
- **`write_gmsl_projection(ds, path)`** writes it as compressed netCDF4.

ipccar5's [`service.py`](https://github.com/fact-sealevel/ipccar5/blob/wire_in_grd/src/ipccar5/service.py)
shows the two ways of calling them:

- **One file per source region** (`run_icesheets`): a dict of
  `source_region -> (samples, output path)`, looping over it and calling
  `make_gmsl_ds` / `write_gmsl_projection` for each output path that was given.
- **One file with many source regions** (`run_glaciers`, regions output): the regional
  samples stacked on a last axis, with a list of `source_region` keys.

Write the samples as float64. Both approaches keep the CLI pattern of one
`--...-output-file` option per file written.

### 2. Choose your `budget_term` and `source_region` keys

- Use one fixed `budget_term` per module command (ipccar5: `"glaciers"`, `"icesheets"`),
  defined as a constant in your code rather than a CLI option.
- Define `source_region` keys for each region your module projects. They are
  determined by which calculation produced the data, so set them in code, not from
  file names or CLI arguments.
- Keys must be unique across the whole fingerprint map. grd looks them up across every
  section of the map and uses the first match.

### 3. Create a fingerprint map for your module

Save it as `data/input/mappings/<module>_fingerprintmap.yml` and put the fingerprint
files it references in `data/input/fingerprint/<module>/`:

```yaml
<budget_term>:
   <source_region key>:
      fingerprint: FPRINT/<fingerprint file>.nc
```

- Top-level section names are for readability; grd ignores them.
- Paths must start with `FPRINT/`. grd replaces that prefix with `--fingerprint-dir`.
- Several keys may share a fingerprint file (ipccar5's `rgi14` and `rgi15` both use
  `fprint_glac7.nc`).
- Leave out totals that overlap their parts (ipccar5 has no `ais` or glacier `global`
  entry), so passing them by mistake raises
  `Source region ... has no matching entry in the fingerprint map` instead of
  double counting.

### 4. Check it

- Run grd once per budget term and check its log lines list every source region with
  the intended fingerprint.
- If your module previously did its own localization, compare against that output on
  the same inputs. For ipccar5, glaciers matched exactly and ice sheets matched to
  float32 rounding.
- Add a test that every `source_region` key your module can write is present in your
  fingerprint map, so the two can't drift apart.

## Appendix: ipccar5 fingerprint map

`data/input/mappings/ipccar5_fingerprintmap.yml`:

```yaml
# GRD Fingerprint Map: ipccar5
#
# Maps each source_region written by the ipccar5 module to its fingerprint in
# data/input/fingerprint/ipccar5/. Keys must match ipccar5's source_region values.
#
# Glaciers: RGI first-order regions (Kopp14 / Marzeion 2012). RGI 19 (Antarctic
# periphery) is not projected by ipccar5.
# Icesheets: 'ais' (= wais + eais) and the glaciers 'global' total are left out on
# purpose, so passing them raises an error rather than double counting.

glaciers:
   rgi01:
      fingerprint: FPRINT/fprint_glac11.nc  # Alaska
   rgi02:
      fingerprint: FPRINT/fprint_glac12.nc  # WesternCanUS
   rgi03:
      fingerprint: FPRINT/fprint_glac14.nc  # ArcticCanadaNorth
   rgi04:
      fingerprint: FPRINT/fprint_glac13.nc  # ArcticCanadaSouth
   rgi05:
      fingerprint: FPRINT/fprint_gis.nc     # GreenlandGIC
   rgi06:
      fingerprint: FPRINT/fprint_glac1.nc   # Iceland
   rgi07:
      fingerprint: FPRINT/fprint_glac2.nc   # Svalbard
   rgi08:
      fingerprint: FPRINT/fprint_glac10.nc  # Scandinavia
   rgi09:
      fingerprint: FPRINT/fprint_glac3.nc   # RussianArctic
   rgi10:
      fingerprint: FPRINT/fprint_glac5.nc   # NorthAsia
   rgi11:
      fingerprint: FPRINT/fprint_glac9.nc   # CentralEurope
   rgi12:
      fingerprint: FPRINT/fprint_glac8.nc   # Caucasus
   rgi13:
      fingerprint: FPRINT/fprint_glac6.nc   # CentralAsia
   rgi14:
      fingerprint: FPRINT/fprint_glac7.nc   # SouthAsiaWest
   rgi15:
      fingerprint: FPRINT/fprint_glac7.nc   # SouthAsiaEast
   rgi16:
      fingerprint: FPRINT/fprint_glac15.nc  # LowLatitudes
   rgi17:
      fingerprint: FPRINT/fprint_glac16.nc  # SouthernAndes
   rgi18:
      fingerprint: FPRINT/fprint_glac17.nc  # NewZealand

icesheets:
   gis:
      fingerprint: FPRINT/fprint_gis.nc
   wais:
      fingerprint: FPRINT/fprint_wais.nc
   eais:
      fingerprint: FPRINT/fprint_eais.nc
```
