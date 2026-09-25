import re
import time

import numpy as np
import xarray as xr
import yaml

def read_map_file(grd_fp_map_file: str) -> dict:
    with open(grd_fp_map_file, "r") as file:
        grd_fp_dict = yaml.safe_load(file)

    return grd_fp_dict

def ReadLocationFile(location_file):
    # Initialize variables to hold data and site information
    names = []
    ids = []
    lats = []
    lons = []

    # Compile the regex for finding commented lines
    comment_regex = re.compile(r"^#")

    # Open the rate file
    with open(location_file, "r") as f:
        # Loop over the lines of the file
        for line in f:
            # Skip commented lines
            if re.search(comment_regex, line):
                continue

            # Split the line into components
            (this_name, this_id, this_lat, this_lon) = line.split("\t")

            # Store the information
            names.append(this_name)
            ids.append(int(this_id))
            lats.append(float(this_lat))
            lons.append(float(this_lon))

    # Cast everything as numpy arrays
    names = np.array(names)
    ids = np.array(ids)
    lats = np.array(lats)
    lons = np.array(lons)

    # Return variables
    return (names, ids, lats, lons)

def read_gmsl_projections(projection_files):
    # Load every GMSL projection file and stack their 'budget_term'/
    # 'source_region' dims into a single 'combo' dimension carrying a
    # (budget_term, source_region) MultiIndex, then concatenate along that
    # dimension. Unlike combining along 'budget_term' and 'source_region' as
    # two independent dimensions, this keeps the sparse budget_term/
    # source_region pairing intact instead of expanding it into a mostly-NaN
    # budget_term x source_region grid.
    combo_datasets = []
    for gmsl_file in projection_files:
        ds = xr.open_dataset(gmsl_file).load()
        ds.close()
        combo_datasets.append(ds.stack(combo=("budget_term", "source_region")))

    return xr.concat(combo_datasets, dim="combo")


def write_localized_projections(
    rsl,
    site_ids,
    site_lats,
    site_lons,
    scenario,
    baseyear,
    budget_term,
    targyears,
    output_path,
):
    # Define the missing value for the netCDF files
    nc_missing_value = np.nan  # np.iinfo(np.int16).min

    # Create the xarray data structures for the localized projections
    ncvar_attributes = {
        "description": "Local SLR contributions according to emulandice2",
        "history": "Created " + time.ctime(time.time()),
        "source": "SLR Framework: emulandice2 workflow",
        "scenario": scenario,
        "baseyear": baseyear,
        "budget_term": budget_term,
    }

    (nsamps, nyears, nregions) = rsl.shape
    rsl_out = xr.Dataset(
        {
            "sea_level_change": (
                ("samples", "years", "locations"),
                rsl,
                {"units": "mm", "missing_value": nc_missing_value},
            ),
            "lat": (("locations"), site_lats),
            "lon": (("locations"), site_lons),
        },
        coords={
            "samples": np.arange(nsamps),
            "years": targyears,
            "locations": site_ids,
        },
        attrs=ncvar_attributes,
    )

    rsl_out.to_netcdf(
        output_path,
        encoding={
            "sea_level_change": {
                "dtype": "f4",
                "zlib": True,
                "complevel": 4,
                "_FillValue": nc_missing_value,
            }
        },
    )

    return None
