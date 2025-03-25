#! /usr/bin/env python

from __future__ import print_function

import numpy as np
from astropy.coordinates import SkyCoord
from astropy import units as u

FLOAT_TYPES = [float, np.float32, np.float64]

def dd_hms_dms(ra, dec, delim=":"):
    """Convert from DD to HMS:DMS."""

    if np.array([isinstance(ra, t) for t in FLOAT_TYPES]).any():

        coords = SkyCoord(ra=ra, dec=dec, unit=(u.deg, u.deg))
        str_coords = coords.to_string(style="hmsdms").split()

        if delim == ":":
            ra = str_coords[0].replace("h", ":").replace("m", ":").replace("s", "")
            dec = str_coords[1].replace("d", ":").replace("m", ":").replace("s", "")
        else:
            ra = str_coords[0]
            dec = str_coords[1]
    
    return ra, dec

def main():
    from argparse import ArgumentParser

    ps = ArgumentParser(description="Convert from dd.dd to hms:dms.")
    ps.add_argument("ra", type=float)
    ps.add_argument("dec", type=float)
    ps.add_argument("-d", "--delimiter", type=str, default=":")

    args = ps.parse_args()
    ra, dec = dd_hms_dms(ra=args.ra, dec=args.dec, delim=args.delimiter)

    print("{} {}".format(ra, dec))

if __name__ == "__main__":
    main()