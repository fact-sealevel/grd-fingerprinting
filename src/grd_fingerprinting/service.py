from grd_fingerprinting.io import (
    read_map_file,
    ReadLocationFile,
    write_localized_projections,
    ReadFingerprint as readfp
)
from scipy import interpolate as interp

import xarray as xr
import numpy as np
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

    grd_fp_dict = read_map_file(
        grd_fp_map_file=grd_fingerprint_map_file
    )

    #Organize projection netcdf files by regions from grd fp dict
    matching_ncfiles_dict = process_ncfiles(projection_files, grd_fp_dict=grd_fp_dict)

    # Read location file
    (_, site_ids, site_lats, site_lons) = ReadLocationFile(location_file=location_file)

    # Make dict of rsl projections
    rsl_dict, targyears = scale_ncfiles_by_fingerprint(
        matching_ncfiles_dict,
        grdfingerprint_dict=grd_fp_dict,
        site_lats=site_lats,
        site_lons=site_lons,
        chunksize=chunksize,
        fingerprint_dir=fingerprint_dir
    )

    for ice_source, rsl in rsl_dict.items():
        if len(rsl):
            print(ice_source)
            write_localized_projections(
                rsl=rsl,
                site_ids=site_ids,
                site_lats=site_lats,
                site_lons=site_lons,
                scenario=scenario,
                baseyear=baseyear,
                ice_source=ice_source,
                targyears=targyears,
                output_path=output_lslr_file
            )

def process_ncfiles(ncfiles, grd_fp_dict):
    
    # Initialize the dictionary to store the matching netcdf files
    matching_ncfiles_dict = {}

    # Loop through the grdfingerprintfile
    for ice_source, regions in grd_fp_dict.items():
        for region, regionvars in regions.items():
            # Initialize an empty list for this region
            matching_ncfiles_dict[region] = []

            # Loop through the ncfiles
            for ncfile in ncfiles:
                # Open the netcdf file
                ds = xr.open_dataset(ncfile)
                # Check if the 'region' global attribute matches the current region
                if "region" in ds.attrs and ds.attrs["region"] == region:
                    # If it matches, add the ncfile to the list for this region
                    matching_ncfiles_dict[region].append(ncfile)

                # Close the dataset
                ds.close()

    return matching_ncfiles_dict

def scale_ncfiles_by_fingerprint(
    matching_ncfiles_dict,
    grdfingerprint_dict,
    site_lats,
    site_lons,
    chunksize,
    fingerprint_dir,
):
    # Initialize the	 dictionary to store the scaled and summed netcdf files
    scaled_ncfiles_dict = {}

    targyears = None
    # Loop over all the ice sources in grdfingerprint_dict
    for ice_source, regions in grdfingerprint_dict.items():
        # Initialize an empty array for this ice source
        scaled_ncfiles_dict[ice_source] = []

        # Loop over each region
        for region, regionvars in regions.items():
            # Check if there is a non-empty list of files in matching_ncfiles_dict
            if region in matching_ncfiles_dict and matching_ncfiles_dict[region]:
                # Load the fingerprint for that region
                regionfp = da.array(
                    AssignFP(
                        regionvars["fingerprint"].replace("FPRINT", fingerprint_dir),
                        site_lats,
                        site_lons,
                    )
                )
                regionfp = regionfp.rechunk(chunksize)

                # Loop over the matching netcdf files
                for ncfile in matching_ncfiles_dict[region]:
                    print(region + ": " + ncfile)

                    # Load the netcdf file
                    ds = xr.open_dataset(ncfile)

                    # Initialize variable to hold the localized projections
                    ## global should be locations=0, but Tamsin is currently using a different convention.
                    samps = (
                        ds["sea_level_change"]
                        .isel(locations=-1)
                        .transpose("samples", "years")
                    )

                    # Scale the netcdf file by the fingerprint
                    # NOT SURE WHY NP CONVERSIONS HERE ARE NEEDED, IT WORKED IN OTHER MODULES WITHOUT
                    local_sl = np.multiply.outer(samps.values, np.array(regionfp))

                    # Add the resulting scaled netcdf file to the array for this ice source
                    if len(scaled_ncfiles_dict[ice_source]):
                        scaled_ncfiles_dict[ice_source] += local_sl
                    else:
                        scaled_ncfiles_dict[ice_source] = local_sl

                    targyears = ds["years"]

                    # Close the dataset
                    ds.close()

    return scaled_ncfiles_dict, targyears

def AssignFP(fp_filename, qlats, qlons):
    ## Read in the fitted parameters from parfile
    # Open the file
    (fp, fp_lats, fp_lons) = readfp(fp_filename)

    # Interpolate the fingerprint to these locations
    lat_sort = np.argsort(fp_lats)
    fp_interp = interp.RectBivariateSpline(
        fp_lats[lat_sort], fp_lons, fp[lat_sort, :], kx=1, ky=1
    )
    fp_sites = fp_interp.ev(qlats, np.mod(qlons, 360)) * 1000

    return fp_sites