#!/usr/bin/env python
# Script original developed by John Morgan (JM)
# Example invocation from JM
# make_imstack.py 1204233560_IPS --suffixes=image -n 207
import os, sys, psutil, datetime, logging, h5py, contextlib
import numpy as np
# from optparse import OptionParser #NB zeus does not have argparse!
from argparse import ArgumentParser
from astropy.io import fits

VERSION = "0.2"
#changes from 0.1: lzf instead of gzip, support new wsclean which does not have WSCTIMES and WSCTIMEE
CACHE_SIZE = 1024 #MB
N_PASS = 1
TIME_INTERVAL = 4
TIME_INDEX = 0
POLS = 'I'
STAMP_SIZE = 16
SLICE = [0, 0, slice(None, None, None), slice(None, None, None)]
HDU = 0
PB_THRESHOLD = 0.1 # fraction of pbmax
#SUFFIXES=["image", "model", "dirty"]
SUFFIXES = "image,model"
N_TIMESTEPS = 25
N_CHANNELS = 1
DTYPE = np.float16
FILENAME = "{prefix}-t{time:04d}-{suffix}.fits"
PB_FILE = "{prefix}-beam.fits"

parser = ArgumentParser(
    description="Convert a set of wsclean images into an hdf5 image cube"
)
parser.add_argument('prefix', type=str, help='The prefix of file names to dump into the hdf5 file')
parser.add_argument("-n", default=N_TIMESTEPS, type=int, help="number of timesteps to process [default: %default]")
parser.add_argument("--start", default=TIME_INDEX,  type=int, help="starting time index [default: %default]")
parser.add_argument("--step", default=TIME_INTERVAL, type=float, help="time between timesteps [default: %default]")
parser.add_argument("--outfile", default=None, type=str, help="outfile [default: [prefix].hdf5]")
parser.add_argument("--suffixes", default=SUFFIXES, type=str, help="comma-separated list of suffixes to store [default: %default]")
parser.add_argument("--stamp-size", default=STAMP_SIZE, type=int, help="hdf5 stamp size [default: %default]")
parser.add_argument("--check-filenames-only", action="store_true",  help="check all required files are present then quit.")
parser.add_argument("--allow-missing", action="store_true",  help="check for presence of files for contiguous timesteps from --start up to -n")
parser.add_argument('-v','--verbose', action='store_true', default=False, help='More output logging')

args = parser.parse_args()

prefix = args.prefix

logging.basicConfig(format='%(asctime)s-%(levelname)s %(message)s', level=logging.INFO)
if args.verbose:
    logging.basicConfig(format='%(asctime)s-%(levelname)s %(message)s', level=logging.DEBUG)

if args.outfile is None:
    args.outfile = "%s.hdf5" % prefix

if os.path.exists(args.outfile):
    logging.warning("Warning: editing existing file")
    file_mode = "r+"
else:
    file_mode = "w"

args.suffixes = args.suffixes.split(',')

# check that all image files are present
for suffix in args.suffixes:
    for t in range(args.start, args.n+args.start):
        infile = FILENAME.format(prefix=prefix, time=t, suffix=suffix)
        if not os.path.exists(infile):
            if args.allow_missing:
                new_n = t-args.start
                logging.info("couldn't find file %s: reducing n from %d to %d", infile, args.n, new_n)
                args.n = new_n
                break
            raise IOError("couldn't find file %s" % infile)
        logging.debug("%s found", infile)

if args.check_filenames_only:
    sys.exit()

propfaid = h5py.h5p.create(h5py.h5p.FILE_ACCESS)
settings = list(propfaid.get_cache())
settings[2] *= CACHE_SIZE
propfaid.set_cache(*settings)

with contextlib.closing(h5py.h5f.create(args.outfile.encode("utf-8"), fapl=propfaid)) as fid:
    df = h5py.File(fid, file_mode)

df.attrs['VERSION'] = VERSION
df.attrs['USER'] = os.environ['USER']
df.attrs['DATE_CREATED'] = datetime.datetime.utcnow().isoformat()

group = df['/']
group.attrs['TIME_INTERVAL'] = args.step

# determine data size and structure
image_file = FILENAME.format(prefix=prefix, time=args.start, suffix=args.suffixes[0])
hdus = fits.open(image_file, memmap=True)
image_size = hdus[HDU].data.shape[-1]
assert image_size % args.stamp_size == 0, "image_size must be divisible by stamp_size"
data_shape = [1, image_size, image_size, N_CHANNELS, args.n] # first axis is for polarisations
logging.debug("data shape: %s" % data_shape)
chunks = (1, args.stamp_size, args.stamp_size, N_CHANNELS, args.n)

pb_mask = np.ones(data_shape[1:-1] + [1], dtype=bool)
pb_nan = np.ones(data_shape[1:-1] + [1])

# write main header information
timestep_start = group.create_dataset("timestep_start", (args.n,), dtype=np.uint16)
timestep_stop = group.create_dataset("timestep_stop", (args.n,), dtype=np.uint16)
timestamp = group.create_dataset("timestamp", (args.n,), dtype="S21")
header_file = FILENAME.format(prefix=prefix, time=args.n//2, suffix=args.suffixes[0])

# add fits header to attributes
hdus = fits.open(header_file, memmap=True)
header = group.create_dataset('header', data=[], dtype=DTYPE)
for key, item in hdus[0].header.items():
    header.attrs[key] = item

for s, suffix in enumerate(args.suffixes):
    logging.info("processing suffix %s" % (suffix))
    logging.info("about to allocate data %s", psutil.virtual_memory())

    if s == 0:
        data = np.zeros(data_shape, dtype=DTYPE)
    else:
        data *= 0
    filenames = group.create_dataset("%s_filenames" % suffix, (1, N_CHANNELS, args.n), dtype="S%d" % len(header_file), compression='lzf')

    n_rows = image_size
    i=0
    for t in range(args.n):
        im_slice = [slice(n_rows*i, n_rows*(i+1)), slice(None, None, None)]
        fits_slice = tuple(SLICE[:-2] + im_slice)

        infile = FILENAME.format(prefix=prefix, time=t+args.start, suffix=suffix)
        logging.info(" processing %s", infile)
        with fits.open(infile, memmap=True) as hdus:
            filenames[0, 0, t] = infile.encode("utf-8")
            data[0, n_rows*i:n_rows*(i+1), :, 0, t] = np.where(pb_mask[n_rows*i:n_rows*(i+1), :, 0, 0],
                                                            hdus[0].data[fits_slice],
                                                            np.nan)*pb_nan[n_rows*i:n_rows*(i+1), :, 0, 0]
            if s == 0:
                timestamp[t] = hdus[0].header['DATE-OBS'].encode("utf-8")
                timestep_start[t] = t
                timestep_stop[t] = t+1
            else:
                assert timestamp[t] == hdus[0].header['DATE-OBS'].encode("utf-8"), "Timesteps do not match %s in %s" % (args.suffixes[0], infile)
    logging.info(" writing to hdf5 file")
    hdf5_data = group.create_dataset(suffix, data_shape, chunks=chunks, dtype=DTYPE, compression='lzf', shuffle=True)
    hdf5_data[...] = data
    logging.info(" done with %s" % suffix)