#! /usr/bin/env python
# Author: Stefan Duchesne, piip


import sys
c = 299792458.0

def baseline(freq, lambdas):
    """
    """

    wl = c / (freq*1.e6)
    metres = wl * lambdas

    return metres

def main():
    """
    """

    freq = float(sys.argv[1])
    lambdas = float(sys.argv[2])
    print(baseline(freq, lambdas))

if __name__ == "__main__":
    main()
