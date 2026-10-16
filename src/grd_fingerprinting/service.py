from grd_fingerprinting.io import (
    read_map_file,
    ReadLocationFile,
    write_localized_projections,
    read_gmsl_projections,
)
from scipy import interpolate as interp

import numpy as np
import xarray as xr
import dask.array as da


def run_fingerprinting(
        location_file,
        chunksize,
        projection_files,
        grd_fingerprint_map_file,
        fingerprint_dir,
        output_lslr_file,
        scenario,
        baseyear,
):

    # Load the region -> fingerprint-file mapping, and all GMSL projection
    # files into a single dataset with a (budget_term, source_region)
    # MultiIndex 'combo' dimension.
    grd_fp_dict = read_map_file(grd_fp_map_file=grd_fingerprint_map_file)
    gmsl_ds = read_gmsl_projections(projection_files)
    check_single_budget_term(
        gmsl_ds.indexes["combo"].get_level_values("budget_term")
    )

    # Read location file
    (_, site_ids, site_lats, site_lons) = ReadLocationFile(location_file=location_file)

    # Make dict of rsl projections, keyed by budget_term
    rsl_dict, targyears = scale_projections_by_fingerprint(
        gmsl_ds=gmsl_ds,
        grd_fp_dict=grd_fp_dict,
        fingerprint_dir=fingerprint_dir,
        site_lats=site_lats,
        site_lons=site_lons,
        chunksize=chunksize,
    )

    for budget_term, rsl in rsl_dict.items():
        if len(rsl):
            print(budget_term)
            write_localized_projections(
                rsl=rsl,
                site_ids=site_ids,
                site_lats=site_lats,
                site_lons=site_lons,
                scenario=scenario,
                baseyear=baseyear,
                budget_term=budget_term,
                targyears=targyears,
                output_path=output_lslr_file
            )


def check_single_budget_term(budget_terms):
    # Each run localizes one budget term and writes it to --output-lslr-file;
    # with more than one, each would overwrite the last.
    found = sorted(set(budget_terms))
    if len(found) > 1:
        raise ValueError(
            f"Projection files contain multiple budget terms {found}. "
            "grd-fingerprinting must be run once per budget term."
        )


def find_fingerprint_file(grd_fp_dict, source_region, fingerprint_dir):
    # grd_fp_dict is nested budget_category -> source_region -> {"fingerprint": path}.
    # Search across every category for a source_region key match; the yml's
    # fingerprint paths are of the form "FPRINT/<file>.nc", so swap the
    # "FPRINT" prefix for the actual --fingerprint-dir.
    for regions in grd_fp_dict.values():
        if source_region in regions:
            return regions[source_region]["fingerprint"].replace("FPRINT", fingerprint_dir)

    return None


def scale_projections_by_fingerprint(
    gmsl_ds,
    grd_fp_dict,
    fingerprint_dir,
    site_lats,
    site_lons,
    chunksize,
):
    # Initialize the dictionary to store the scaled and summed projections,
    # accumulated per budget_term across all of its source_regions.
    scaled_dict = {}

    targyears = gmsl_ds["year"].values

    # Loop over every distinct (budget_term, source_region) pair present in
    # the GMSL projections.
    combos = sorted(set(gmsl_ds.indexes["combo"].tolist()))
    for budget_term, source_region in combos:
        # Look up this source_region's fingerprint file in the map; skip any
        # source_region with no matching entry.
        fp_filename = find_fingerprint_file(grd_fp_dict, source_region, fingerprint_dir)
        if fp_filename is None:
            raise ValueError(
                f"Source region {source_region} in GMSL projections has no matching entry in the fingerprint map."
            )

        print(source_region + ": " + budget_term + " -> " + fp_filename)

        # Load the fingerprint for that region
        regionfp = da.array(
            AssignFP(
                fp_filename,
                site_lats,
                site_lons,
            )
        )
        regionfp = regionfp.rechunk(chunksize)

        # Select this budget_term/source_region's sea level change samples
        samps = (
            gmsl_ds["sea_level_change"]
            .sel(combo=(budget_term, source_region))
            .transpose("sample", "year")
        )

        # Scale the projection by the fingerprint
        # NOT SURE WHY NP CONVERSIONS HERE ARE NEEDED, IT WORKED IN OTHER MODULES WITHOUT
        local_sl = np.multiply.outer(samps.values, np.array(regionfp))

        # Add the resulting scaled projection to the array for this
        # budget_term, summing contributions across all of its source_regions.
        if len(scaled_dict.setdefault(budget_term, [])):
            scaled_dict[budget_term] += local_sl
        else:
            scaled_dict[budget_term] = local_sl

    return scaled_dict, targyears

def AssignFP(fp_filename, qlats, qlons):
    ## Open this region's fingerprint file directly
    fp_ds = xr.open_dataset(fp_filename)
    fp = fp_ds["fp"].transpose("lat", "lon").values
    fp_lats = fp_ds["lat"].values
    fp_lons = fp_ds["lon"].values
    fp_ds.close()

    # Interpolate the fingerprint to these locations
    lat_sort = np.argsort(fp_lats)
    fp_interp = interp.RectBivariateSpline(
        fp_lats[lat_sort], fp_lons, fp[lat_sort, :], kx=1, ky=1
    )
    fp_sites = fp_interp.ev(qlats, np.mod(qlons, 360)) * 1000

    return fp_sites
