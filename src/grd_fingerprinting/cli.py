import click
from grd_fingerprinting.service import run_fingerprinting

@click.command()
@click.option(
    "--location-file",
    type=str,
    required=True,
    help="path to file holding location info"
)

@click.option(
    "--chunksize",
    type=int,
    help="number of locations to process at once"
)
@click.option(
    "--projection-files",
    multiple=True,
    required=True,
    help="Paths to GMSL projection netcdfs to be converted to RSL",
)
@click.option(
    "--grd-fingerprint-map-file",
    type=str,
    required=True,
    help="Path to grd fingerprint region mapping file"
)
@click.option(
    "--fingerprint-dir",
    required=True,
    type=str,
    help="Path to directory containing fingerprint netcdf files"
)
@click.option(
    "--output-lslr-file",
    type=str,
    required=True,
    help="name of output file to write"
)
@click.option(
    "--scenario",
    type=str,
    required=True,
    help = "emissions scenario"
)
@click.option(
    "--baseyear",
    type=int,
    required=True,
    help="Base year to which projections are centered"
)
def main(
    location_file,
    chunksize,
    projection_files,
    grd_fingerprint_map_file,
    fingerprint_dir,
    output_lslr_file,
    scenario,
    baseyear
):
    click.echo("Hello from GRD Fingerprinting!")
    
    run_fingerprinting(
        location_file=location_file,
        chunksize=chunksize,
        projection_files=projection_files,
        grd_fingerprint_map_file=grd_fingerprint_map_file,
        fingerprint_dir=fingerprint_dir,
        output_lslr_file=output_lslr_file,
        scenario=scenario,
        baseyear=baseyear
    )