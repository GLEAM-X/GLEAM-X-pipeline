#!/usr/bin/env python

from astropy.io import fits
from astropy.table import Table, Row
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.wcs import WCS
from astropy.nddata import Cutout2D
from astropy.coordinates import Angle
from astropy.units import hourangle, deg
from reproject import reproject_adaptive
import numpy as np
from subprocess import run, CompletedProcess, CalledProcessError, PIPE, STDOUT
import logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from argparse import ArgumentParser
from matplotlib import pyplot as plt
from ARZU_PlExPy.ARZU_PlExPy import setFonts
from matplotlib import use
use("Agg")
setFonts()

logger = logging.getLogger("make_timeseries")
logger.propagate = False
stream_handler = logging.StreamHandler()
# Format: [2024-06-01 12:00:00] [INFO] Message
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.setLevel(logging.INFO)

def render_transient_visuals(src: Row, catalog_files: list[Path], outbase: str, verbose: bool = False):
    if verbose:
        logger.setLevel(logging.DEBUG)
    n_inp = len(catalog_files)
    obsids = np.array([cat.stem.split("_")[0] for cat in catalog_files])
    first_cutout_size = 500
    second_cutout_size = 200

    # Get some source stats
    pos = SkyCoord(src['mean_ra'], src['mean_dec'], unit=(u.deg, u.deg), frame='fk5')
    radec = pos.to_string('hmsdms', sep=":", precision=1)
    ra, dec = pos.to_string('hmsdms', sep="", precision=0).split(" ")
    srcname = f"MWA_J{ra}{dec}"
    eta, var = src['eta'], src['var']
    fluxes = np.array([src[f'peak_flux_{i+1}'] for i in range(0, n_inp)])
    errs = np.array([np.sqrt((0.01*src[f'peak_flux_{i+1}'])**2 + src[f'local_rms_{i+1}']**2) for i in range(0, n_inp)])
    # errs = np.array([np.sqrt((0.1*src[f'peak_flux_{i+1}'])**2 + src[f'local_rms_{i+1}']**2) for i in range(0, n_inp)])
    outliers = np.where(fluxes > src['median_flux'] + 5*src['mad_flux'])[0]

    # Clean up any old images from previous runs
    temp_images = Path.cwd().glob(f"{outbase}_{srcname}_???.png")
    for f in temp_images:
        logger.debug("Removing old image %s", f)
        f.unlink()

    # Make a light curve
    fig, ax = plt.subplots(figsize=(16,10))
    ax.set_title(fr"Pos = {radec}   SNR = {src['snr']:.1f}   $\eta =${eta:.1f}   $V =${var:.1f}")
    if src['snr'] > 10:
        color = 'red'
    else:
        color = 'grey'
    logger.debug("Rendering light curve and cutouts for %s", srcname)
    ax.errorbar(x=range(n_inp), y=fluxes, yerr=errs, fmt='-o', lw=1, color=color, mfc='black', mec='black', capsize=5)
    for i, flux, obsid in zip(outliers, fluxes[outliers], obsids[outliers]):
        ax.annotate(obsid, (i, flux), textcoords="offset points", xytext=(0,15), ha='center', fontsize=16, color='blue')

    # ax.set_ylim([-3*np.nanmin(errs), 1.1*np.nanmax(fluxes)])
    ax.set_ylabel("Flux density (Jy/beam)")
    ax.set_xlabel("Time (arbitrary units)")
    ax.grid()
    fig.savefig(f"{outbase}_{srcname}_lightcurve.png", bbox_inches="tight", dpi=128)
    plt.close(fig)

    # Make an animated gif
    ref_img_header: fits.Header = fits.open(str(catalog_files[0]).replace('_comp', ''))[0].header
    for i in range(0, n_inp):
        img = str(catalog_files[i]).replace('_comp', '')
        imghdu = fits.open(img)
        w = WCS(imghdu[0].header, naxis=2)
        # For some reason, some of my images are flattened (8000,8000) and others are not! (1, 1, 8000, 8000)
        logger.debug("imghdu[0].data.shape: %s", imghdu[0].data.shape)
        if imghdu[0].data.shape[0] == 1:
            cutout = Cutout2D(imghdu[0].data[0,0], pos, (first_cutout_size, first_cutout_size), wcs = w)
        else:
            cutout = Cutout2D(imghdu[0].data, pos, (first_cutout_size, first_cutout_size), wcs = w)

        # Re-project the image to a common WCS so that the animation doesn't jitter around
        reprojected_image = reproject_adaptive((cutout.data, cutout.wcs), ref_img_header, return_footprint=False, parallel=True, roundtrip_coords=False)
        logger.debug("Reprojected cutout shape for catalog %d/%d: %s", i + 1, n_inp, reprojected_image.shape)

        cutout = Cutout2D(reprojected_image, pos, (second_cutout_size, second_cutout_size), wcs = WCS(ref_img_header, naxis=2))

        fig = plt.figure(figsize=(3,3))
        ax = plt.subplot(projection=w)
        ax.imshow(cutout.data, origin="lower", vmax=np.nanmean(cutout.data)+5*np.nanstd(cutout.data))
        plt.axis("off")
        plt.margins(x=0)
        plt.margins(y=0)
        fig.savefig(f"{outbase}_{srcname}_{i:03d}.png", bbox_inches="tight", dpi=64, pad_inches=0)
        plt.close(fig)

    try:
        result: CompletedProcess = run(f"convert -delay 35 {outbase}_{srcname}_???.png {outbase}_{srcname}_animation.gif", shell=True, stdout=PIPE, stderr=STDOUT, check=True, text=True)
        logger.info("Created animation and light curve products for %s", srcname)
    except CalledProcessError as e:
        logger.error("Error occurred while creating animation: %s", e)
        logger.error(f"Logs from convert: {result.stdout}")

    temp_images = Path.cwd().glob(f"{outbase}_{srcname}_???.png")
    for f in temp_images:
        if not (int(f.stem.split("_")[-1]) in outliers):
            f.unlink()
            logger.debug("Removed temporary image %s", f)

def hms_to_deg(hms: str) -> float:
    """Convert a string in the format 'HH:MM:SS' to degrees

    Args:
        hms (str): String in the format 'HH:MM:SS'

    Returns:
        float: The equivalent value in degrees
    """
    try:
        return Angle(hms, unit=hourangle).degree
    except ValueError as err:
        logger.error(f"Invalid HMS format for RA: {hms}. Expected format is 'HH:MM:SS'. Error details: {err}")
        raise err

def dms_to_deg(dms: str) -> float:
    """Convert a string in the format 'DD:MM:SS' to degrees

    Args:
        dms (str): String in the format 'DD:MM:SS'

    Returns:
        float: The equivalent value in degrees
    """
    try:
        return Angle(dms, unit=deg).degree
    except ValueError as err:
        logger.error(f"Invalid DMS format for Dec: {dms}. Expected format is 'DD:MM:SS'. Error details: {err}")
        raise err

if __name__ == "__main__":
    parser = ArgumentParser(description="Search for transients within a group of source catalogs")
    parser.add_argument("catalogs", nargs="+", type=Path, help="The source catalogs to search for transients in. These should be the 'comp' catalogs produced by AEGEAN 2.0. An ASCII file listing the catalogs can also be provided, with one catalog path per line.")
    parser.add_argument("-o", "--outbase", type=Path, default="", help="The base name for the output files")
    parser.add_argument("-x", "--extract-src", action="store_true", help="Extract light curve of a specific source and make the corresponding GIF (requires --ra and --dec)")
    parser.add_argument("--ra", type=str, help="Right ascension of the source to be extracted (in Sexagesimal format: 'hh:mm:ss')")
    parser.add_argument("--dec", type=str, help="Declination of the source to be extracted (in Sexagesimal format: '+dd:mm:ss')")
    parser.add_argument("--xradius", type=float, default=180, help="Radius in arcseconds for internal source matching (default: 180)")
    parser.add_argument("-j", "--jobs", type=int, default=1, help="The number of parallel jobs to use")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print out more info about what I'm doing")
    args = parser.parse_args()

    try:
        with open(args.catalogs[0]) as f:
            catalog_files = [Path(line.strip()) for line in f]
        cat_list: Path = args.catalogs[0]
    except (UnicodeDecodeError):
        catalog_files: list[Path] = args.catalogs

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info(f"Starting transient search for {len(catalog_files)} catalog(s)")
    logger.info(f"Writing outputs to files with base name {args.outbase}")
    output_catalog = Path(f"{args.outbase}_isocompact_crossmatched_catalog.fits")

    minra = 0.0
    maxra = 360
    mindec = -90
    maxdec = 90
    for cat in catalog_files:
        logger.debug(f"Reading catalog bounds from {cat}")
        tab = Table(fits.open(cat)[1].data)
        minra = np.nanmax([minra, np.nanmin(tab["ra"])])
        maxra = np.nanmin([maxra, np.nanmax(tab["ra"])])
        mindec = np.nanmax([mindec, np.nanmin(tab["dec"])])
        maxdec = np.nanmin([maxdec, np.nanmax(tab["dec"])])

    # Shave off a small margin -- this avoids really terrible parts of the images
    minra+=1.5
    maxra-=1.5
    mindec+=1.5
    maxdec-=1.5
    logger.info(f"Restricted search region to RA {minra:.3f}..{maxra:.3f} deg, Dec {mindec:.3f}..{maxdec:.3f} deg")

    # Create a matched table with STILTS
    n_inp = len(catalog_files)
    logger.info(f"Crossmatching {n_inp} catalog(s) with {args.xradius} arcsec sky radius")

    # Downselect to sources within the region we care about
    # Note the slightly frustrating quotes
    # Also removing any source where the peak flux was fitted but with a '-1' error -- these are very poor fits and should not be used
    icmd = "".join([f"icmd{i+1}=\'select \"ra > {minra} && ra < {maxra} && dec < {maxdec} && dec > {mindec} && err_peak_flux > -1 && err_a > -1\"\' " for i in range(0, n_inp)])
    # Always include an entry -- a transient could be in a single frame
    joincmd = "".join([f"join{i+1}='always' " for i in range(0, n_inp)])
    # Sky crossmatch of 180" was found to be necessary -- this is not the ionosphere, this is sources being decomposed in different ways
    valuescmd = "".join([f"values{i+1}='ra dec' " for i in range(0, n_inp)])
    incmd = "".join([f"in{i+1}={catalog_files[i]} " for i in range(0, n_inp)])
    stiltscmd = f"nin={n_inp} matcher='sky' params={args.xradius} multimode='group' out={output_catalog} {incmd} {icmd} {valuescmd} {joincmd}"
    # logger.debug("Running STILTS command: stilts tmatchn %s", stiltscmd)
    run(f"stilts tmatchn {stiltscmd}", shell=True, check=True)

    logger.info(f"Loading matched catalog from {output_catalog}")
    jointab = Table(fits.open(output_catalog)[1].data)
    logger.info(f"Matched table contains {len(jointab)} rows")

    # Have to select compactness after join or we will occasionally mark slightly extended sources as transient
    # We have to do a (NOT EXTENDED) because that also includes the 'NaN' sources, i.e. non-detections
    masks = np.empty((n_inp, len(jointab)), dtype='bool')
    for i in range(0, n_inp):
        logger.debug(f"Computing compactness mask for catalog {i + 1}")
        masks[i, :] = ~(jointab[f"int_flux_{i+1}"]/jointab[f"peak_flux_{i+1}"] > 1.5)

    # The final mask is the sources that are nan or compact
    compact_mask = np.nanmin(masks, axis=0)
    logger.info(f"Compact source selection kept {np.count_nonzero(compact_mask)}/{len(compact_mask)} rows")

    # We want to find out the average RAs of all the sources and the average Decs of all the sources so that we can look up where they are in the maps if we need to
    jointab['mean_ra'] = np.nanmean([jointab[f'ra_{i+1}'] for i in range(0, n_inp)], axis=0)
    jointab['mean_dec'] = np.nanmean([jointab[f'dec_{i+1}'] for i in range(0, n_inp)], axis=0)
    coords = SkyCoord(jointab['mean_ra'], jointab['mean_dec'], frame='fk5', unit=(u.deg, u.deg))
    # We also want to know the rough centroid of the observations so we can exclude the edges
    cent = SkyCoord(np.median(jointab['mean_ra']), np.median(jointab['mean_dec']), frame='fk5', unit=(u.deg, u.deg))
    spatial_mask = coords.separation(cent) < 9.5*u.deg
    logger.info(f"Spatial cut kept {np.count_nonzero(spatial_mask)}/{len(spatial_mask)} rows")
    # We will later want the average flux density of sources BEFORE we have populated them with zeros
    jointab['mean_on_peak_flux'] = np.nanmean([jointab[f'peak_flux_{i+1}'] for i in range(0, n_inp)], axis=0)
    jointab['mean_on_local_rms'] = np.nanmean([jointab[f'local_rms_{i+1}'] for i in range(0, n_inp)], axis=0)

    # Now we have compact transient sources in a reliable region, for every missing entry, go and look up the flux/RMS in the associated flux/RMS map (just take the value at that pixel).
    # Downselecting the sources a bit here helps with the RAM management which can otherwise blow up
    bscales = np.empty(n_inp, dtype='float32')
    for i in range(0, n_inp):
        logger.debug(f"Backfilling missing flux and RMS values for catalog {i + 1}")
        mask = np.logical_and(compact_mask,np.logical_and(spatial_mask, np.isnan(jointab[f'int_flux_{i+1}'])))
        logger.debug(f"Catalog {i + 1} has {np.count_nonzero(mask)} missing entries to backfill")

        rmsmap = str(catalog_files[i]).replace('comp', 'rms')
        rmshdu = fits.open(rmsmap, 'update')
        # some bscale values are empty for some reason!
        try:
            b = rmshdu[0].header['BSCALE']
        except KeyError:
            rmshdu[0].header['BSCALE'] = 1.0
            rmshdu.close()
            rmshdu = fits.open(rmsmap)
        w = WCS(rmshdu[0].header, naxis=2)
        index = w.world_to_array_index(coords[mask])
        try:
            rms = rmshdu[0].data[index]
        except IndexError:
            logger.warning("A source has coordinates outside the bounds of the RMS map; setting local RMS to 0.")
            rms = 0
        jointab[f'local_rms_{i+1}'][mask] = rms

        img = str(catalog_files[i]).replace('_comp', '')
        imghdu = fits.open(img, mode='update')
        # Sometimes BSCALE isn't a key word for some reason
        try:
            bscales[i] = imghdu[0].header['BSCALE']
        except KeyError:
            # logger.warning("%s is missing BSCALE; setting it to 1.0", img)
            imghdu[0].header['BSCALE'] = 1.0
            bscales[i] = 1.0
        # some bscale values are empty for some reason!
        if imghdu[0].header['BSCALE'] is None:
            # logger.warning("%s has an empty BSCALE; setting it to 1.0", img)
            bscales[i] = 1.0
            imghdu[0].header['BSCALE'] = 1.0
            imghdu.close()
            imghdu = fits.open(img)
        w = WCS(imghdu[0].header, naxis=2)
        index = w.world_to_array_index(coords[mask])
        # For some reason, some of my images are flattened (8000,8000) and others are not! (1, 1, 8000, 8000)
        if imghdu[0].data.shape[0] == 1:
            try:
                flux = imghdu[0].data[0,0][index]
            except IndexError:
                logger.warning("A source has coordinates outside the bounds of the image; setting flux to 0.")
                flux = 0
        else:
            try:
                flux = imghdu[0].data[index]
            except IndexError:
                logger.warning("A source has coordinates outside the bounds of the image; setting flux to 0.")
                flux = 0
        # flux = np.max(flux, 0)
        jointab[f'int_flux_{i+1}'][mask] = flux
        jointab[f'peak_flux_{i+1}'][mask] = flux
        logger.debug(f"Finished backfilling catalog {i + 1}")

    # We need some summary stats for the next bit to work
    fluxes = np.empty((n_inp, len(jointab)), dtype='float32')
    sigmas = np.empty((n_inp, len(jointab)), dtype='float32')
    for i in range(0, n_inp):
        fluxes[i, :] = jointab[f"peak_flux_{i+1}"] * bscales[i]
        sigmas[i, :] = jointab[f"local_rms_{i+1}"]
        # Add the errors in quadrature -- suppresses the apparent variability of bright sources (just flux density calibrator errors and ionosphere)
        # sigmas[i, :] = np.sqrt((0.1*jointab[f'peak_flux_{i+1}'] * bscales[i])**2 + (jointab[f"local_rms_{i+1}"])**2)
    wfluxes = fluxes * sigmas**-2
    weights = sigmas**-2
    jointab['weighted_avg_peak_flux'] = np.nanmean(wfluxes, axis=0) / np.nanmean(weights, axis=0)
    jointab['mean_peak_flux'] = np.nanmean(fluxes, axis=0)
    logger.info("Computed weighted mean and mean peak flux statistics")

    innerterm = np.empty((n_inp, len(jointab)), dtype='float32')
    fluxsq = np.empty((n_inp, len(jointab)), dtype='float32')
    # Compute the inner terms for eta and var
    for i in range(0, n_inp):
        logger.debug(f"Computing variability terms for catalog {i + 1}")
        innerterm[i, :] = ((jointab[f"peak_flux_{i+1}"] * bscales[i] - jointab['weighted_avg_peak_flux'])**2) / (jointab[f"local_rms_{i+1}"]**2 + (0.1*jointab[f"peak_flux_{i+1}"] * bscales[i])**2)
        fluxsq[i, :]  = (jointab[f"peak_flux_{i+1}"] * bscales[i])**2

    # With our completed table, we can run an eta/V analysis.
    jointab['eta'] = (1 / (n_inp - 1)) * np.nansum(innerterm, axis=0)
    jointab['var'] = (1 / jointab['mean_peak_flux']) * np.sqrt((n_inp/(n_inp-1)) * (np.nanmean(fluxsq, axis=0) - jointab['mean_peak_flux']**2))
    logger.info("Computed eta and variability metrics")

    fluxes = np.array([jointab[f'peak_flux_{i+1}'] * bscales[i] for i in range(0, n_inp)])
    jointab['median_flux'] = np.median(fluxes, axis=0)
    jointab['mad_flux'] = np.median(np.absolute(fluxes - jointab['median_flux']), axis=0)
    jointab['snr'] = (np.max(fluxes, axis=0) - jointab['median_flux']) / jointab['mad_flux']

    # Identify all internal matches within 2' using STILTS
    logger.info("Identifying internal matches within 120 arcsec")
    jointab.write('tmp.fits', format='fits', overwrite=True)

    logger.debug("Running STILTS command: stilts tmatch1 matcher='sky' values='mean_ra mean_dec' params=120 action=identify in=tmp.fits out=sparse.fits")
    run("stilts tmatch1 matcher='sky' values='mean_ra mean_dec' params=120 action=identify in=tmp.fits out=sparse.fits", shell=True, check=True)

    # Read that back in, and then write out the final table which should consist only of compact, isolated sources within the useful region of the images
    try:
        jointab = Table(fits.open('sparse.fits')[1].data)
        logger.info("Loading sparsified catalog from sparse.fits")
        iso_mask = ~(jointab['GroupSize'] > 1)
        logger.info(f"Isolation cut kept {np.count_nonzero(iso_mask)}/{len(iso_mask)} rows")
        final_mask = np.logical_and(np.logical_and(compact_mask, iso_mask), spatial_mask)
    except FileNotFoundError:
        logger.info("No internal matches found within 120 arcsec; proceeding with original matched catalog")
        final_mask = np.logical_and(compact_mask, spatial_mask)
    logger.info(f"Final selection kept {np.count_nonzero(final_mask)}/{len(final_mask)} rows")
    jointab[final_mask].write(f"{output_catalog}", format='fits', overwrite=True)
    logger.info(f"Wrote final catalog to {output_catalog}")
    # Write everything while we're debugging
    # jointab.write('modified_join_table.fits', format='fits', overwrite=True)
    # Clean up my mess
    for temp_file in (Path("tmp.fits"), Path("sparse.fits")):
        try:
            temp_file.unlink()
            logger.debug(f"Removed temporary file {temp_file}")
        except FileNotFoundError:
            logger.warning(f"Temporary file {temp_file} was already missing during cleanup", temp_file)

    if args.extract_src:
        if args.ra is None or args.dec is None:
            logger.error("RA and Dec are required for source extraction")
            exit(1)

        logger.info(f"Extracting source at RA: {args.ra}, Dec: {args.dec}")
        pos = SkyCoord(hms_to_deg(args.ra), dms_to_deg(args.dec), unit=(u.deg, u.deg), frame='fk5')

        # Find the closest source in the final catalog to the specified coordinates
        # The fluxes in this Gaussian fitted catalog are not reliable for extended sources, so these will be replaced with the fluxes from the island catalogs
        coords = SkyCoord(jointab['mean_ra'], jointab['mean_dec'], unit=(u.deg, u.deg), frame='fk5')
        idx, sep2d, _ = pos.match_to_catalog_sky(coords)
        if sep2d.arcsecond[0] > args.xradius:
            logger.error(f"No source found within {args.xradius} arcseconds of the specified coordinates")
            exit(1)
        src = jointab[idx] # This is compatible with the plotting function

        mean_pos = SkyCoord(src['mean_ra'], src['mean_dec'], unit=(u.deg, u.deg), frame='fk5')
        mean_ra, mean_dec = mean_pos.to_string('hmsdms', sep="", precision=0).split(" ")
        logger.info(f"Found source at RA: {mean_ra}, Dec: {mean_dec} (J2000), separation: {sep2d.arcsecond[0]:.2f} arcseconds from requested position.")

        for i in range(0, n_inp):
            island_catalog = Table(fits.open(str(catalog_files[i]).replace('comp', 'isle'))[1].data)

            # Find the closest source in the island catalog to the specified coordinates
            island_coords = SkyCoord(island_catalog['ra'], island_catalog['dec'], unit=(u.deg, u.deg), frame='fk5')
            island_idx, island_sep2d, _ = pos.match_to_catalog_sky(island_coords)
            if island_sep2d.arcsecond[0] > args.xradius:
                logger.warning(f"No source found within {args.xradius} arcseconds of the specified coordinates in catalog {catalog_files[i]}")
                src[f'peak_flux_{i+1}'] = 0.0
            else:
                logger.debug(f"Found source in catalog {catalog_files[i]} at RA: {island_catalog['ra'][island_idx]}, Dec: {island_catalog['dec'][island_idx]} (J2000), separation: {island_sep2d.arcsecond[0]:.2f} arcseconds from requested position.")
                src[f'peak_flux_{i+1}'] = island_catalog[island_idx]['int_flux'] * bscales[i]

        fluxes = np.array([src[f'peak_flux_{i+1}'] for i in range(0, n_inp)])
        src['median_flux'] = np.median(fluxes, axis=0)
        src['mad_flux'] = np.median(np.absolute(fluxes - src['median_flux']), axis=0)
        src['snr'] = (np.max(fluxes, axis=0) - src['median_flux']) / src['mad_flux']

        logger.info(f"The transient (MAD-based) SNR (calculated from island fluxes) of the source is: {src['snr']:.2f}")
        render_transient_visuals(src, catalog_files, args.outbase, args.verbose)
    else:
        # Select interesting sources and make useful plots
        eta_var_sanity_mask = np.logical_and(jointab['eta'] > 0.0, jointab['var'] > 0.0)
        eta_cut = 2
        var_cut = 0.2
        # Plot eta and var against each other, and then select interesting sources
        plt.figure(figsize=(16,16))
        plt.scatter(jointab['eta'][eta_var_sanity_mask], jointab['var'][eta_var_sanity_mask], s=10, color='blue', alpha=0.5)
        plt.axhline(y=var_cut, color='red', linestyle='--', alpha=0.7)
        plt.axvline(x=eta_cut, color='red', linestyle='--', alpha=0.7)
        # Use logarithmic axes to make the plot more readable
        plt.xscale('log')
        plt.yscale('log')
        plt.xlabel(r'$\eta$')
        plt.ylabel(r'$V$')
        plt.title("Variability metrics for sources in matched catalog")
        plt.grid()
        plt.savefig(f"{'_'.join(cat_list.stem.split('_')[1:]) if cat_list else catalog_files[0].stem}_eta_var_scatter.png", bbox_inches="tight")
        plt.close()

        eta_mask = jointab['eta'] > eta_cut
        var_mask = jointab['var'] > var_cut
        brightness_mask = jointab['mean_on_peak_flux']/jointab['mean_on_local_rms'] > 3
        transient_snr_mask = jointab['snr'] > 5
        transients_mask = np.logical_and(np.logical_and(np.logical_and(final_mask, eta_mask), var_mask), np.logical_and(brightness_mask, transient_snr_mask))
        logger.info(f"Transient selection kept {np.count_nonzero(transients_mask)}/{len(transients_mask)} rows")
        logger.info("Generating plots for selected transient candidates")
        
        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            futures = []
            for src in jointab[transients_mask]:
                futures.append(executor.submit(render_transient_visuals, src, catalog_files, args.outbase, args.verbose))
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing source: {e}")
