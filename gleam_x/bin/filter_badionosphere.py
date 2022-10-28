#!/usr/bin/env python

""" Script to assess the quality of obsid images and identify high quality images to include in mosaic step. 

TODO: generalise to run for night rather than per channel. Make sure to check percentage of missing per night to log issue rather than just a raw number

TODO: add plotting options 

"""


from ast import parse
from mmap import mmap
import sys
import os
from argparse import ArgumentParser
from astropy.coordinates import SkyCoord, search_around_sky
from astropy.io import fits
from matplotlib import pyplot as plt
import astropy.units as u
import numpy as np
import logging 
import matplotlib.ticker as ticker
from matplotlib import rcParams
import matplotlib.pyplot as plt
import cmasher as cmr


logger = logging.getLogger(__name__)
logging.basicConfig(format="%(module)s:%(levelname)s:%(lineno)d %(message)s")
logger.setLevel(logging.INFO)


rcParams['font.family'] = 'serif'
s, dt, axlab = 8, 1.1, 12.
plt.rcParams["xtick.major.size"] = s
plt.rcParams["xtick.minor.size"] = s
plt.rcParams["ytick.major.size"] = s
plt.rcParams["ytick.minor.size"] = s
plt.rcParams["xtick.major.width"] = dt
plt.rcParams["xtick.minor.width"] = dt
plt.rcParams["ytick.major.width"] = dt
plt.rcParams["ytick.minor.width"] = dt
plt.rcParams["xtick.direction"] = 'in'
plt.rcParams["ytick.direction"] = 'in'
plt.rcParams["xtick.major.pad"] = 5.
plt.rcParams["figure.figsize"] = [10., 4.5]

def read_obsids(filename):

    try: 
        channel_obsids = np.loadtxt(f"{args.project}/{filename}")
    except FileNotFoundError:
        logger.warning(f"Cannot find txt file with obsids: {args.project}/{filename}")
        channel_obsids = []
    return channel_obsids


def remove_missing(obsids_list):
    
    good_obsids = []
    missing_obsids = []

    for obsid in obsids_list:
        if os.path.exists(f"{base_dir}/{obsid:10.0f}/{obsid:10.0f}_deep-MFS-image-pb_warp_rescaled_comp.fits") is True: 
            good_obsids.append(obsid)
        else:
            logger.debug(f"No catalogue for io checks: {obsid:10.0f}")
            missing_obsids.append(obsid)

    logger.debug(f"Number of missing obsids: {len(missing_obsids)}")
    if len(missing_obsids)>5:
        logger.warning(f"Large number of missing obsids: {len(missing_obsids)}/{len(obsids_list)}")

    return good_obsids, missing_obsids


def cut_high_rms(obsids_list):

    rms = []
    ra = []
    
    for i in range(len(obsids_list)):
        rmsfile = f"{args.project}/{obsids_list[i]:10.0f}/{obsids_list[i]:10.0f}_deep-MFS-image-pb_warp_rms.fits"
        if os.path.exists(rmsfile):
            # TODO: plotobs.append(obs)
            hdu = fits.open(rmsfile)
            rms.append(1.e3*hdu[0].data[int(hdu[0].data.shape[0]/2), int(hdu[0].data.shape[1]/2)])
            ra.append(hdu[0].header["CRVAL1"])
            hdu.close()
        else:
            logger.debug(f"Found missing obsid while checking RMS, make sure ran check for missing earlier")
            rms.append(np.nan)
            ra.append(np.nan)


    cutoff = np.nanmedian(rms)+np.nanstd(rms)
    obslist_rmscut = obsids_list[rms<cutoff]
    obslist_badrms = obsids_list[rms>=cutoff]

    frac_flagged = int((1-(len(obslist_rmscut)/len(obsids_list)))*100)
    if frac_flagged > 15:
        logger.warning(f"Large number of obsids flagged for high RMS: {frac_flagged}%")

    return obslist_rmscut, obslist_badrms


def crossmatch_cats(
    input_cat,
    ref_cat,
    sep=1,
):

    ref_cat_skycoords = SkyCoord(ref_cat.RAJ2000,ref_cat.DEJ2000, frame='fk5',unit=u.deg)
    input_cat_skycoords = SkyCoord(input_cat.ra, input_cat.dec, frame='fk5', unit=u.deg)

    idx, d2d, d3d = input_cat_skycoords.match_to_catalog_sky(ref_cat_skycoords)
    sep_constraint = d2d < sep*u.arcmin
    output_cat = input_cat[sep_constraint]
    # output_cat = input_cat[idx]

    return output_cat 

def check_io(obsid):

    # for i in range(len(obsids_list)):
    catfile = f"{args.project}/{obsid:10.0f}/{obsid:10.0f}_deep-MFS-image-pb_warp_rms.fits"
    if os.path.exists(catfile):
        hdu = fits.open(catfile)
        temp_cat = hdu[1].data
        hdu.close()
    else:
        logger.debug(f"Found missing obsid while checking src quality, make sure ran check for missing earlier")
        return 
        
    int_over_peak = temp_cat["int_flux"]/temp_cat["peak_flux"]
    err_intoverrms = temp_cat["err_int_flux"]/temp_cat["local_rms"]
    snr = temp_cat["int_flux"]/temp_cat["local_rms"]   
    shape = temp_cat["a"]/temp_cat["b"]

    mask = np.where((int_over_peak<=2)&(err_intoverrms<=2)&(snr>=5))
    cat = temp_cat[mask]

    if args.plot == "all":
        plt_io_obsid(int_over_peak[mask], shape[mask], f"{obsid:10.0f}")

    cat_xm = crossmatch_cats(cat, args.refcat)


    return cat_xm, [np.nanmean(int_over_peak[mask]), np.nanstd(int_over_peak[mask])], [np.nanmean(shape[mask]),np.nanstd(shape[mask])]



def plt_io_obsid(
    intoverpeak,
    shape,
    obsid,
    ext="png",
):

    # Just plotting the shape compared to int/flux 
    fig = plt.figure(dpi=plt.rcParams['figure.dpi']*4.0)
    ax = fig.add_subplot(1,1,1)

    ax.scatter(intoverpeak,shape,s=50, color="C6")
    ax.axhline(1,color="k",alpha=0.3, linestyle="--")

    ax.set_xlabel("int_flux/peak_flux")
    ax.set_ylabel("shape (a/b)")
    fig.suptitle(f"{obsid}: Int/peak vs shape")

    plt.savefig(f"{args.project}/{obsid}/{obsid}_intoverpeak_shape.{ext}", bbox_inches='tight')

    return 

def plt_io_pernight(
    obslist,
    intoverpeak,
    std_intoverpeak,
    shape,
    drift,
    ext="png",
):
    colors=cmr.take_cmap_colors(
        "cmr.flamingo", len(obslist), cmap_range=(0.4, 0.7), return_fmt="hex"
    )
    fig = plt.figure(dpi=plt.rcParams['figure.dpi']*4.0)
    ax = fig.add_subplot(1,1,1)
    for i in range(len(obslist)):
        ax.errorbar(obslist[i], intoverpeak[i],yerr=(std_intoverpeak[i]/np.sqrt(len(obslist[i]))), fmt="o", color=colors[i])
    ax.axhline(np.nanmean(intoverpeak), color="k", alpha=0.3, linestyle="--")
    # ax.axvline(1.15, color="k", alpha=0.3, linestyle="--")
    ax.set_ylabel(f"mean(int/peak)")
    ax.set_xlabel(f"obsid")
    fig.suptitle(f"{drift}: Int/Peak")
    plt.savefig(f"{args.project}/{drift}/{drift}_intoverpeak.{ext}", bbox_inches='tight')


    fig = plt.figure(dpi=plt.rcParams['figure.dpi']*4.0)
    ax = fig.add_subplot(1,1,1)
    for i in range(len(obslist)):
        chan_intoverpeak = intoverpeak[i]
        chan_shape = shape[i]
        chan_obslist = obslist[i]
        for j in range(len(chan_obslist)):
            chanobs_intoverpeak = np.nanmean(chan_intoverpeak[j])
            chanobs_shape = np.nanmean(chan_shape[j])
            ax.scatter(chanobs_intoverpeak,chanobs_shape, fmt="o", color=colors[i])
    ax.axhline(1, color="k", alpha=0.3, linestyle="--")
    ax.axvline(1, color="k", alpha=0.3, linestyle="--")
    ax.set_ylabel(f"mean(a/b)")
    ax.set_xlabel(f"mean(int/peak)")
    fig.suptitle(f"{drift}: Int/Peak vs shape")
    plt.savefig(f"{args.project}/{drift}/{drift}_intoverpeak_shape.{ext}", bbox_inches='tight')
    
    return 



if __name__ == "__main__":
    parser = ArgumentParser(
        description="Script to assess the quality of images for obsids and return list of obsids that pass quality assurance to be included in moasics. Note: currently only works on obsids given per channel, not per night. "
    )
    parser.add_argument(
        '--project',
        type=str,
        default=".",
        help="Path to project directory containing obsid folders, also where the drift scan folder is containing text files $project/$drift/*.txt (default= ./)"
    )
    parser.add_argument(
        'obsids',
        type=str,
        help="The text file of obsids to be processed. Will work out if its .txt or cenchan_chan.txt, at most plz $project/drift/drift.txt, no extra directories "
    )
    parser.add_argument(
        '--refcat',
        type=str,
        default="GGSM_sparse_unresolved.fits",
        help="reference catalogue to crossmatch and get only bright, unresolved and sparse sources. (default=./GGSM_sparse_unresolved.fits)"
    )

    parser.add_argument(
        '--flag_high_rms',
        default=True,
        help='Will only select obsids that have RMS no larger than the median RMS at that freq channel + the STD of the RMS of the night'
    )
    parser.add_argument(
        '--flag_bad_io',
        default=True,
        help="Will run cuts on the quality of sources in each obsid then calculate int/peak etc. to assess io per obsid and over night "
    )
    parser.add_argument(
        "--plot",
        default="all",
        type=str,
        help="Level of plotting to do: all, min, none",
    )

    parser.add_argument(
        '--save_missing_obsids',
        default=None,
        help="If defined, will make a .txt file in directory with all obsids with no *MFS-image-pb_warp_rms.fits file (default=None)"
    )
    parser.add_argument(
        '--save_bad_obsids',
        default=None,
        help="Will make a .txt file with the bad obsids (default=None) "
    )



    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        default=False,
        help='Enable extra logging'
    )



    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    

    base_dir = args.project
    txtfile = args.obsids 
    refcat=  args.refcat
    logger.debug(f"{txtfile}")

    # Reading in the list of obsids: will deal with the cenchan or all based on what the input txt file is called 
    if "cenchan" in txtfile:
        logger.debug(f"Only detected one cenchan, proceeding with just 1")
        obs_txtfile = [txtfile]
        split_string = txtfile.split("/")
        if len(split_string) == 2: 
            split_string = split_string[-1].split("_cenchan_")
            drift = split_string[0]
            chans = [split_string[1].split(".")[0]]
        elif len(split_string)==1:
            split_string = split_string[0].split("_cenchan_")
            chans = [split_string[1].split(".")[0]]
            drift = split_string[0]
        logger.debug(f"drift: {drift}")
        logger.debug(f"cenchan: {chans[0]}")
    else: 
        split_string = txtfile.split("/")
        logger.debug(f"Detected no cenchan, proceeding with allchans")
        if len(split_string) == 2:
            drift = split_string[-1].replace(".txt", "")
        elif len(split_string) == 1:
            drift = split_string[0].replace(".txt","")
        logger.debug(f"drift: {drift}")
        chans = ["069", "093", "121", "145", "169"]
        obs_txtfile = []
        for chan in chans:
            obs_txtfile.append(txtfile.replace(".txt",f"_cenchan_{chan}.txt"))


    # Looking for any missing obsids so they're removed before assessing 
    logger.debug(f"{obs_txtfile}")
    # Reading in the obsids from txt files
    obsids_perchan = []
    for i in range(len(chans)):
        cenchan_obsids = read_obsids(obs_txtfile[i])
        cenchan_good_obsids, cenchan_missing_obsids = remove_missing(cenchan_obsids)
        obsids_perchan.append(cenchan_good_obsids)
        logger.debug(f"{len(obsids_perchan)}")

        if args.save_missing_obsids is not None: 
            logger.debug(f"Saving missing obsids")
            np.savetxt(obs_txtfile[i].replace(".txt", "_missing_obsids.txt"), cenchan_missing_obsids, fmt="%10.0f")

    
    # Cutting obsids with high RMS in MFS image 
    # TODO: ACTUALLY DOWNLOAD SOME OBSIDS TO CHECK 
    if args.flag_high_rms is True: 
        obsids_postrms = []
        obsids_badrms = []
        for i in range(len(chans)):
            logger.debug(f"{obsids_perchan[i]}")
            obsids_postrms_temp, obsids_badrms_temp = cut_high_rms(obsids_perchan[i])
            obsids_postrms.append(obsids_postrms_temp)
            obsids_badrms.append(obsids_badrms_temp)

            if args.save_bad_obsids is not None:
                logger.debug(f"Saving bad rms obsids")
                np.savetxt(obs_txtfile[i].replace(".txt", "_bad_obsids.txt"), cenchan_missing_obsids, fmt="%10.0f")
    else: 
        logger.debug(f"Not running the high RMS cut")
        obsids_postrms = obsids_perchan

    # Running cut of bad sources to assess io
    # note: first cuts bad srcs, the xm with GGSM to find nice brihgt etc ones before doing the actually assessment 
    # TODO: have removed cut levels as variables, I think it should be ok and keeps it clean but check later 
    if args.flag_bad_io is True: 
        drift_meanintoverpeak = []
        drift_stdintoverpeak = []
        drift_meanshape = []
        drift_stdshape = []
        for i in range(len(chans)):
            logger.debug(f"Running the io check")
            obslist_iochecks = obsids_postrms[i]
            obs_meanintoverpeak = []
            obs_stdintoverpeak = []
            obs_meanshape = []
            obs_stdshape = []
            for o in range(len(obslist_iochecks)):
                cat_xm, obs_intoverpeak_temp, obs_shape_temp = check_io(obslist_iochecks[o])
                obs_meanintoverpeak.append(obs_intoverpeak_temp[0])
                obs_stdintoverpeak.append(obs_intoverpeak_temp[1])
                obs_meanshape.append(obs_shape_temp[0])
                obs_stdshape.append(obs_shape_temp[1])
            drift_meanintoverpeak.append(obs_meanintoverpeak)
            drift_stdintoverpeak.append(obs_stdintoverpeak)
            drift_meanshape.append(obs_meanshape)
            drift_stdshape.append(obs_stdshape)
        if args.plot in ["all", "min"]:
            plt_io_pernight(obsids_postrms, drift_meanintoverpeak, drift_stdintoverpeak, drift_meanshape,drift)


            



