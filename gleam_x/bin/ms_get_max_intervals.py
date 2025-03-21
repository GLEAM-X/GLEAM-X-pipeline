#! /usr/bin/env python
# Author: Stefan Duchesne, piip

import sys
import numpy as np

from casacore.tables import table


def intervals(ms):
    f = table(ms, ack=False)
    print(len(np.unique(f.getcol("TIME"))))


if __name__ == "__main__":
    intervals(sys.argv[1])
