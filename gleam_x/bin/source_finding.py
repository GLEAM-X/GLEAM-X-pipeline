from argparse import ArgumentParser
from astropy.io import fits
from astropy.wcs import WCS
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.nddata import Cutout2D
from pathlib import Path
from subprocess import run, PIPE, STDOUT
import logging

def configure_logger(name: str = "flag_bad_channels", level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        # Format: [2024-06-01 12:00:00] [INFO] Message
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger

def make_cutouts(image_files: list[Path], ra_dec_center: str, cutout_size: float, output_directory: Path, logger: logging.Logger) -> list[Path]:
    """
    Create cutouts of the image around the specified coordinates using astropy.

    Parameters:
    - image_files: A list of paths to the input image files.
    - ra_dec_center: The RA and Dec coordinates (in J2000) to center the cutouts on, in the format 'RA Dec' (e.g., '01:08:52.86 +13:20:13.8').
    - cutout_size: The size of the cutouts in degrees.
    - output_directory: The directory to save the cutout files.
    - logger: The logger for logging messages.
    """

    cutout_center = SkyCoord(ra_dec_center, unit=(u.hourangle, u.deg))
    cutout_size = cutout_size * u.deg
    cutout_files = []

    for image_file in image_files:
        # logger.debug(f"{type(image_file)}, {image_file}, {image_file.stem}, {cutout_files}")
        cutout_files.append(output_directory / f"{image_file.stem}_cutout_{cutout_size.value:.0f}-deg.fits")

        with fits.open(image_file) as hdul:
            original_header = hdul[0].header.copy()
            wcs = WCS(hdul[0].header, fix=False)
            cutout = Cutout2D(hdul[0].data[0, 0, :, :], cutout_center, cutout_size, wcs=wcs.celestial)

        cutout_wcs_header = cutout.wcs.to_header()

        keys_to_set = ["BSCALE", "BZERO", "BUNIT", "BMAJ", "BMIN", "BPA", "BTYPE", "TELESCOP", "OBSERVER", "OBJECT", "ORIGIN"]
        for key in keys_to_set:
            cutout_wcs_header.set(key, original_header[key], original_header.comments[key])

        # Create a new FITS file for the cutout
        cutout_hdu = fits.PrimaryHDU(data=cutout.data, header=cutout_wcs_header)
        cutout_hdu.writeto(cutout_files[-1], overwrite=True)
        logger.info(f"Cutout created successfully for {cutout_files[-1]} with {cutout.data.shape} pixels.")

    return cutout_files

def run_BANE_and_aegean(container: Path, image_files: list[Path], output_directory: Path, logger: logging.Logger) -> list[Path]:
    """
    Run BANE and aegean from AEGEAN 2.0 on the input image files to create source catalogs.

    Parameters:
    - container: The path to the Singularity container to use.
    - image_files: A list of paths to the input image files.
    - output_directory: The directory to save the output catalog files.
    - logger: The logger for logging messages.
    """

    catalog_files = []
    for image_file in image_files:
        # Construct the commands to run BANE and aegean. The command will be run for each image file.
        command = ["singularity", "run", str(container), "BANE", str(image_file)]
        logger.debug(f"Running command: {' '.join(command)}")
        retry = True
        while retry == True:
            try:
                result = run(command, check=True, stdout=PIPE, stderr=STDOUT, text=True, timeout=60) # Run BANE first to create the background and noise maps
                retry = False
                logger.debug(f"BANE output:")
                logger.debug(result.stdout)
            except Exception as e:
                if e is TimeoutError:
                    logger.error(f"BANE timed out for {image_file} after 60 seconds.")
                    retry = True
                else:
                    logger.error(f"Error running BANE for {image_file}: {e}")
                    retry = False
                    break

        output_catalog = output_directory / f"{image_file.stem}.fits"
        command = ["singularity", "run", str(container), "aegean", "--island", "--autoload", str(image_file), "--table", str(output_catalog)]

        logger.debug(f"Running command: {' '.join(command)}")

        retry = True
        while retry == True:
            try:
                result = run(command, check=True, stdout=PIPE, stderr=STDOUT, text=True, timeout=120) # Run aegean to create the source catalog
                retry = False
                output_catalog = output_catalog.parent / f"{output_catalog.stem}_comp.fits"
                logger.debug(f"aegean output:")
                logger.debug(result.stdout)
                if output_catalog.exists():
                    catalog_files.append(output_catalog)
                    logger.info(f"Source catalog created successfully: {output_catalog.name}")
            except Exception as e:
                if e is TimeoutError:
                    logger.error(f"aegean timed out for {image_file} after 120 seconds.")
                    retry = True
                else:
                    logger.error(f"Error creating source catalog for {image_file}: {e}")
                    retry = False
                    break

    return catalog_files

if __name__ == "__main__":
    parser = ArgumentParser(description="A script to find the sources in (typically, radio) images and create a catalog for each image using AEGEAN 2.0. It optonally creates cutouts of the images around the specified coordinates.")
    parser.add_argument("-f", "--image_files", nargs="+", type=Path, required=True, help="The image files to process. An ASCII file listing the images can also be provided, with one image path per line.")
    parser.add_argument("-o", "--output_directory", default=".", type=Path, help="Directory to save the output catalog files (and optional cutouts).")
    parser.add_argument("-c", "--ra_dec_center", type=str, help="The RA and Dec coordinates (in J2000) to center the cutouts on, in the format 'RA Dec' (e.g., '01:08:52.86 +13:20:13.8').")
    parser.add_argument("-s", "--cutout_size", type=float, default=10.0, help="The size of the cutouts in degrees (default: 10.0 degrees).")
    parser.add_argument("-a", "--container", type=Path, required=True, help="Path to the Singularity container to use for running BANE and aegean.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging for debugging purposes.")
    args = parser.parse_args()

    logger = configure_logger()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        with open(args.image_files[0]) as f:
            image_files = [Path(line.strip()) for line in f]
    except (UnicodeDecodeError):
        image_files: list[Path] = args.image_files
    # Convert to absolute paths
    image_files = [file.resolve() for file in image_files]
    output_directory = args.output_directory.resolve()

    if args.ra_dec_center is not None:
        logger.debug(f"Cutout center: {args.ra_dec_center}")
        logger.debug(f"Cutout size: {args.cutout_size} degrees")
        cutout_files = make_cutouts(image_files, args.ra_dec_center, args.cutout_size, output_directory, logger)
        aegean_input_files = cutout_files
    else:
        logger.debug("No cutout center provided. Skipping cutout creation. Running source finding on the original image files.")
        aegean_input_files = image_files

    run_BANE_and_aegean(args.container, aegean_input_files, output_directory, logger)
