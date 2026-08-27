from netCDF4 import Dataset
import numpy as np
import re
import time
import xarray as xr
import yaml

def read_map_file(grd_fp_map_file:str)->dict:
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

def ReadFingerprint(fname):
    # Open the fingerprint file
    try:
        nc_fid = Dataset(fname, "r")
    except:
        print("Cannot open fingerprint file: {0}\n".format(fname))
        raise

    # Read in the fingerprint data
    fp = nc_fid.variables["fp"][:, :]
    fp_lats = nc_fid.variables["lat"][:]
    fp_lons = nc_fid.variables["lon"][:]

    return (fp, fp_lats, fp_lons)


def write_localized_projections(
    rsl,
    site_ids,
    site_lats,
    site_lons,
    scenario,
    baseyear,
    ice_source,
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
        "ice_source": ice_source,
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
