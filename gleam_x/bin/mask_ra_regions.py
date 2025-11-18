import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from scipy import stats,ndimage
from astropy.coordinates import SkyCoord
from scipy.interpolate import interp2d, RectBivariateSpline, interpn, griddata
from astropy import units as u
from argparse import ArgumentParser


def sigmoid(x, ref_x):
    return 1. / (1. + np.exp(-(x-ref_x)))


def create_sigweight(infits):

    img_fits = fits.open(infits)
    img_shape = img_fits[0].data.shape
    valid_mask = np.isfinite(img_fits[0].data)
    step = 50
    y, x = np.indices([s//step + 2 for s in img_fits[0].data.shape], dtype=np.int32)
    

    x_grid = np.clip(x*step, None, img_fits[0].data.shape[1]-1)
    y_grid = np.clip(y*step, None, img_fits[0].data.shape[0]-1)

    print('Image shape: ', img_shape)
    print('Max Indicies:', np.max(y_grid), np.max(x_grid))
    print('Min Indicies:', np.min(y_grid), np.min(x_grid))

    img_fits.close()

    keep = valid_mask[y_grid.flatten(), x_grid.flatten()].reshape(y_grid.shape)
    # keep = np.ones_like(y_sparse)
        
    x_valid = x_grid[keep]
    y_valid = y_grid[keep]


    wcs = WCS(img_fits[0].header)

    sky_pos_grid = wcs.all_pix2world(x_grid, y_grid, 0)
    sky_pos = wcs.all_pix2world(x_valid, y_valid, 0)

    max_y = np.max(sky_pos[1])
    min_y = np.min(sky_pos[1])

    mask = sky_pos[1] > (max_y - 10)

    points = [(x_grid, y_grid, sky_pos_grid), (x_valid, y_valid, sky_pos)]

    for (xp, yp, sp) in points:

        print('Plotting sky_pos sigma')
        sig_col = np.max(
                (sigmoid(sp[1], max_y-4),
                1-sigmoid(sp[1], min_y+4)),
                axis=0
            ).astype(np.float16)
        print('Finished sigmoid')
    print('Finished')

    sp = sky_pos_grid
    xp = np.array(x_grid).astype(np.int32)
    yp = np.array(y_grid).astype(np.int32)

    sig_col = np.max(
            (sigmoid(sp[1], max_y-4),
            1-sigmoid(sp[1], min_y+4)),
            axis=0
        ).astype(np.float16)


    print(xp.shape, yp.shape, sig_col.shape)

    x_lin = np.arange(img_shape[1], dtype=np.int32)
    y_lin = np.arange(img_shape[0], dtype=np.int32)

    xx, yy = np.meshgrid(x_lin, y_lin)

    print(xx.shape, xx.dtype)

    stripes = 200
    strides = img_shape[1] // stripes

    sp = sky_pos_grid
    xp = np.array(x_grid).astype(np.int32)
    yp = np.array(y_grid).astype(np.int32)

    sig_col = np.max(
            (sigmoid(sp[1], max_y-4),
            1-sigmoid(sp[1], min_y+4)),
            axis=0
        ).astype(np.float16)

    results = []
    i=0
    while i < (img_shape[1]):
        x_lin = np.arange(img_shape[0], dtype=np.int32)
        maxy= min((i+strides),img_shape[1])
        y_lin = np.arange(
                i,maxy,
                dtype=np.int32)
        print(x_lin.max(), y_lin.max())
        yy, xx = np.meshgrid(y_lin, x_lin)


        print('interpolating')
        d = griddata(
                (xp.flatten(), yp.flatten()),
                sig_col.flatten(),
                (yy, xx),
        ).astype(np.float32)
        print(xx.shape, xx.dtype, d.dtype)

        results.append(d)
        if i+strides >= img_shape[1]:
            i = img_shape[1]
        else:
            i+=strides


    dd = np.hstack(results)

    dd[~valid_mask] = np.nan

    print(dd.shape, dd.dtype)




    ddd=1-dd

    return ddd

def make_ra_region(infits, outfits, ra_min, ra_max):

    with fits.open(infits) as hdul:
        data = hdul[0].data.copy()
        header = hdul[0].header
        hdul.close()
        
        w = WCS(header, naxis=2)

        # # Creating pixel coords 
        y_ind, x_ind = np.indices(data.shape)
        indexes = np.column_stack([x_ind.ravel(), y_ind.ravel()])

        ra_im, dec_im = w.all_pix2world(indexes[:,0], indexes[:,1], 0, ra_dec_order=True)
        c_image = SkyCoord(ra=ra_im, dec=dec_im, unit=(u.degree, u.degree), frame='icrs')

        print(max(ra_im)+360, min(ra_im)+360)
        print(c_image.ra.degree)

        # Identify regions outside of desired RA range that needs nulling 
        ra_mask = np.where((c_image.ra.degree <= ra_min) | (c_image.ra.degree >= ra_max))
        ra_indexes = indexes[ra_mask]


        # # Identify the valid regions to keep 
        # ra_mask_valid = np.where((c_image.ra.degree > ra_min) & (c_image.ra.degree < ra_max))
        # valid_indexes = indexes[ra_mask_valid]
        # valid_values = data[valid_indexes[:,1], valid_indexes[:,0]]

        # valid_mask = ~np.isnan(valid_values)
        # valid_indexes = valid_indexes[valid_mask]
        # valid_values = valid_values[valid_mask]

        # print(ra_mask[:,1])

        data[ra_indexes[:,1], ra_indexes[:,0]] = np.nan
        hdu = fits.PrimaryHDU(data=data, header=header)
        hdu.writeto(outfits, overwrite=True)

    return 

def trim(fin, fout):
    """Searches for the four directions (top, bottom, left, right) for the first
    valid row or column, where valid means not made up entirely of NaNs. Essentially
    performs a crop to remove any row or column made up entirely of nan pixels. 

    Arguments:
        fin (str) -- Path to the input fits file with dimensions to crop
        fout (str) -- Path to new output fits file with cropped dimensions
    """
    hdulist = fits.open(fin)
    data = hdulist[0].data
    hdulist.close()
    # turn pixels that are identically zero, into masked pixels
    data[np.where(data == 0.0)] = np.nan

    print(f"Input image shape: {data.shape}")

    imin, imax = 0, data.shape[1] - 1
    jmin, jmax = 0, data.shape[0] - 1

    # select [ij]min/max to exclude rows/columns that are all zero

    for i in range(0, imax):
        imin = i
        if not np.all(np.isnan(data[:, i])):
            break
    print(f"imin: {imin}")

    for i in range(imax, imin, -1):
        imax = i
        if not np.all(np.isnan(data[:, i])):
            break
    print(f"imax: {imax}")

    for j in range(0, jmax):
        jmin = j
        if not np.all(np.isnan(data[j, :])):
            break
    print(f"jmin: {jmin}")

    for j in range(jmax, jmin, -1):
        jmax = j
        if not np.all(np.isnan(data[j, :])):
            break

    print(f"jmax: {jmax}")

    # End index is not inclusive
    hdulist[0].data = data[jmin : (jmax + 1), imin : (imax + 1)]

    print(f"Output data shape: {hdulist[0].data.shape}")

    # recenter the image so the coordinates are correct.
    hdulist[0].header["CRPIX1"] -= imin
    hdulist[0].header["CRPIX2"] -= jmin

    # save
    hdulist.writeto(fout, overwrite=True)
    print("wrote", fout)
    return

def create_weightmap(sigmoidweight,rms):

    rms_fits = fits.open(rms)
    valid_mask = np.isfinite(rms_fits[0].data)
    imshape_zeros = np.zeros(valid_mask.shape)
    imshape_zeros[valid_mask] = 1.

    if args.do_mask is True: 
        dist_to_edge = ndimage.distance_transform_edt(imshape_zeros,sampling=[1000,1000])
        edgemask = dist_to_edge <= np.nanmax(dist_to_edge)/5


        lowercut = np.nanquantile(rms_fits[0].data, 0.45)
        uppercut = np.nanquantile(rms_fits[0].data,0.95)
        rms_mask = rms_fits[0].data <= lowercut
        rms_mask2 = rms_fits[0].data >= uppercut

        combined_rms = np.logical_or(rms_mask,rms_mask2)
        combined_mask = np.logical_and(combined_rms,edgemask)
        rms_fits[0].data[combined_mask] = np.nan 
    
    
    weightmap = sigmoidweight * (1/(rms_fits[0].data**2))

    return weightmap


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Cut fits image to only include RA region of interest, regenerate trimmed fits image and sigmoid weighting with rms image."
    )
    parser.add_argument(
        "infits",
        help="The input image to use for pixels and sky wcs",
    )
    parser.add_argument(
        "rmsfits",
        help="RMS map to use the sigmoid weighting on and produce final weightmap thats input for swarp"
    )
    parser.add_argument(
        "outfits",
        help="Outfile to save the map to"
    )
    parser.add_argument(
        "--mask",
        action="store_true",
        default=False,
        dest="do_mask",
        help="Add a mask for the edges of the weightmap"
    )
    parser.add_argument(
        "--ra_min",
        type=float,
        default=223.0,
        help="Minimum RA to keep in degrees",
    )
    parser.add_argument(
        "--ra_max",
        type=float,
        default=243.0,
        help="Maximum RA to keep in degrees",
    )
    args = parser.parse_args()



    make_ra_region(args.infits, "temp_ra_masked.fits", ra_min=args.ra_min, ra_max=args.ra_max)
    print("Masked main image with RA limits")
    make_ra_region(args.rmsfits, "temp_rms_ra_masked.fits", ra_min=args.ra_min, ra_max=args.ra_max)
    print("Masked RMS image with RA limits")
    
    trim("temp_ra_masked.fits", args.outfits)
    trim("temp_rms_ra_masked.fits", "temp_rms_ra_masked.fits")
    ddd = create_sigweight(args.outfits)
    fits.writeto(args.outfits, ddd, overwrite=True)

    weightmap = create_weightmap(ddd, "temp_rms_ra_masked.fits")
    fits.writeto(args.outfits, weightmap, overwrite=True)
