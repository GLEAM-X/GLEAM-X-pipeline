#!/usr/bin/env python
from __future__ import print_function

import os, logging
from optparse import OptionParser
from calplots.aocal import fromfile
import numpy as np

parser = OptionParser(usage = "usage: %prog inbinfile outbinfile refant" +
"""
Divide through by phase of a single reference antenna
""")
parser.add_option("-v", "--verbose", action="count", default=0, dest="verbose", help="-v info, -vv debug")
parser.add_option("--incremental", action="store_true", dest="incremental", help="incremental solution")
parser.add_option("--preserve_xterms", action="store_true", dest="preserve_xterms", help="preserve cross-terms (default is to set them all to 0+0j)")
opts, args = parser.parse_args()

if len(args) != 3:
    parser.error("incorrect number of arguments")
infilename = args[0]
outfilename = args[1]
refant = int(args[2])

if opts.verbose == 1:
    logging.basicConfig(level=logging.INFO)
elif opts.verbose > 1:
    logging.basicConfig(level=logging.DEBUG)

ao = fromfile(infilename)

ref_phasor = (ao[0, refant, ...]/np.abs(ao[0, refant, ...]))[np.newaxis, np.newaxis, ...]
if opts.incremental:
    logging.warn("incremental solution untested!")
    ao = ao / (ao*ref_phasor)
else:
    ao = ao / ref_phasor

if not opts.preserve_xterms:
    zshape = (1, ao.n_ant, ao.n_chan)
    ao[..., 1] = np.zeros(zshape, dtype=np.complex128)
    ao[..., 2] = np.zeros(zshape, dtype=np.complex128)

ao.tofile(outfilename)
