#! /usr/bin/env python
# Author: Stefan Duchesne, piip


from argparse import ArgumentParser
import numpy as np
from calplots import aocal


def get_args():
    ps = ArgumentParser()
    ps.add_argument("solutions")
    ps.add_argument("-o", "--outname", default=None, type=str)
    return ps.parse_args()



def invert_solutions(solutions, outname):

    ao = aocal.fromfile(solutions)

    for time in range(ao.shape[0]):
        for antenna in range(ao.shape[1]):
            for channel in range(ao.shape[2]):
                data_inv = np.linalg.inv(ao[time, antenna, channel, :].reshape((2,2)))
                ao[time, antenna, channel, :] = data_inv.flatten()
    ao.tofile(outname)

def cli(args):
    if args.outname is None:
        args.outname = "{}_inv.bin".format(
            args.solutions.replace(".bin", "")
        )
    invert_solutions(args.solutions, args.outname)


if __name__ == "__main__":
    cli(get_args())

