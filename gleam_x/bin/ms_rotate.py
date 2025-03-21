#! /usr/bin/env python
# Author: Stefan Duchesne, piip 

import logging
import time as tm


import numpy as np
from numba import njit, float64, complex128, prange
from casacore.tables import table
from astropy.constants import c; c = c.value
from argparse import ArgumentParser
# from radical import phaserotate

logging.basicConfig(format="%(levelname)s (%(module)s): %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# https://github.com/torrance/radical/blob/master/radical/measurementset.py
# modified to remove filtering
class MeasurementSet(object):
    def __init__(self, filename, refant=0, datacolumn=None):
        self.mset = table(filename, readonly=False, ack=False)
        mset = self.mset

        self.antids = np.array(range(0, len(mset.ANTENNA)))
        self.ra0, self.dec0 = mset.FIELD.getcell('PHASE_DIR', 0)[0]

        self.freqs = mset.SPECTRAL_WINDOW.getcell('CHAN_FREQ', 0)
        self.midfreq = np.array([(min(self.freqs) + max(self.freqs)) / 2])
        self.lambdas = c / self.freqs
        self.midlambda = c / self.midfreq

        # Calculate antenna positions wrt refant antenna
        times = sorted(set(mset.getcol('TIME')))
        self.midtime = times[len(times) // 2]
        (_U, _V, _), antennas = -mset.getcol('UVW').T, mset.getcol('ANTENNA2')


        # Force U, V indices to align with antenna IDs
        self.U = np.zeros_like(self.antids, dtype=np.float64)
        self.U[antennas] = _U
        self.V = np.zeros_like(self.antids, dtype=np.float64)
        self.V[antennas] = _V

        # Load data and associated row information
        # Filter out flagged rows, and autocorrelations
        self.filtered = mset
        self.ant1 = self.filtered.getcol('ANTENNA1')
        self.ant2 = self.filtered.getcol('ANTENNA2')
        self.uvw = self.filtered.getcol('UVW')
        self.u_lambda, self.v_lambda, self.w_lambda = self.uvw.T[:, :, None] / self.lambdas
        self._data = None
        self.colnames = mset.colnames()
        if datacolumn is None:
            datacolumn = ["DATA"]
            if "CORRECTED_DATA" in self.colnames:
                datacolumn.append("CORRECTED_DATA")
            if "MODEL_DATA" in self.colnames:
                datacolumn.append("MODEL_DATA")
        self.datacolumn = datacolumn

    @property
    def data(self):
        if self._data is None:
            self._data = [np.complex128(self.mset.getcol(c)) for c in self.datacolumn] 
        return self._data

    @data.setter
    def data(self, data):
        self._data = data

    def __getattr__(self, name):
        return getattr(self.mset, name)


# https://github.com/torrance/radical/blob/master/radical/phaserotate.py
def phase_rotate(uvw, data, ra, dec, ra0, dec0, lambdas):
    # Calculate rotated uvw values
    start = tm.time()
    new_uvw = rotateuvw(uvw, ra, dec, ra0, dec0)
    elapsed = tm.time() - start
    logger.info("Phase rotated uvw elapsed: {}".format(elapsed))

    # Calculate phase offset
    start = tm.time()
    new_data = [woffset(data_i, uvw.T[2], new_uvw.T[2], lambdas) for data_i in data]
    elapsed = tm.time() - start
    logger.info("Phase rotated visibilities elapsed: {}".format(elapsed))
    
    return new_uvw, new_data

# https://github.com/torrance/radical/blob/master/radical/phaserotate.py
def rotateuvw(uvw, ra, dec, ra0, dec0):
    """
    We calculate new uvw values based on existing uvw values. Whilst this has the effect
    of propagating any existing uvw errors, it has the benefit of being mathematically
    self-consistent.

    Adopted from matrix equation 4.1, in Thompson, Moran, Swenson (3rd edition).
    Let (uvw) = r(ra, dec) * (xyz), then this formula is: r(ra, dec) * r^-1(ra0, dec0)
    """
    u, v, w = uvw.T
    uvwprime = np.empty_like(uvw)

    uvwprime[:, 0] = (
        u * np.cos(ra - ra0)
        + v * np.sin(dec0) * np.sin(ra - ra0)
        - w * np.cos(dec0) * np.sin(ra - ra0)
    )
    uvwprime[:, 1] = (
        -u * np.sin(dec) * np.sin(ra - ra0)
        + v * (np.sin(dec0) * np.sin(dec) * np.cos(ra - ra0) + np.cos(dec0) * np.cos(dec))
        + w * (np.sin(dec0) * np.cos(dec) - np.cos(dec0) * np.sin(dec) * np.cos(ra - ra0))
    )
    uvwprime[:, 2] = (
        u * np.cos(dec) * np.sin(ra - ra0)
        + v * (np.cos(dec0) * np.sin(dec) - np.sin(dec0) * np.cos(dec) * np.cos(ra - ra0))
        + w * (np.sin(dec0) * np.sin(dec) + np.cos(dec0) * np.cos(dec) * np.cos(ra - ra0))
    )
    return uvwprime


# https://github.com/torrance/radical/blob/master/radical/phaserotate.py
@njit([complex128[:, :, :](complex128[:, :, :], float64[:], float64[:], float64[:])], parallel=True)
def woffset(data, oldw, neww, lambdas):
    offset = -2j * np.pi * (neww - oldw)
    phase = np.empty_like(data)

    for row in prange(0, phase.shape[0]):
        tmp = offset[row] / lambdas
        for pol in range(0, data.shape[2]):
            phase[row, :, pol] = tmp

    return data * np.exp(phase)


def do_rotate(msname, ra, dec, datacolumn):
    """
    """

    ms = MeasurementSet(msname, datacolumn=datacolumn)
    ra = np.radians(ra)
    dec = np.radians(dec)

    logger.info("Rotating columns: {}".format(ms.datacolumn))
    uvw, rotated = phase_rotate(uvw=ms.uvw, 
        data=ms.data,
        ra=ra,
        dec=dec,
        ra0=ms.ra0,
        dec0=ms.dec0,
        lambdas=ms.lambdas)

    for i in range(len(ms.datacolumn)):
        ms.mset.putcol(ms.datacolumn[i], rotated[i])
    ms.mset.putcol("UVW", uvw)
    ms.mset.flush()
    ms.mset.close()

    field = table(msname+"/FIELD", readonly=False, ack=False)
    field.putcell('PHASE_DIR', 0, np.array([[ra, dec]]))
    field.flush()
    field.close()


def main():
    """
    """
    ps = ArgumentParser()
    ps.add_argument("msname")
    ps.add_argument("ra", type=float)
    ps.add_argument("dec", type=float)
    ps.add_argument("-c", "--datacolumn", "--data-column", 
        dest="datacolumn", type=str, default=None, nargs="*")
    args = ps.parse_args()

    do_rotate(args.msname, args.ra, args.dec, args.datacolumn)


if __name__ == "__main__":
    main()
