#! /usr/bin/env python

from argparse import ArgumentParser

import numpy as np
from calplots.aocal import fromfile


def get_args():

    ps = ArgumentParser()
    ps.add_argument("obsids", nargs="*", type=int)
    ps.add_argument("-A", "--amp_cut", default=50, type=float)
    ps.add_argument("-P", "--phase_cut", default=2., type=float)
    ps.add_argument("-N", "--perc_nan", default=0.3, type=float)
    ps.add_argument("-S", "--solution_stub", default="_solutions1.bin", type=str)
    ps.add_argument("-c", "--clip", default=1000, type=float,
        help="Clip real/imaginary gain solutions above this value.")
    ps.add_argument("-o", "--outname", default=None)
    ps.add_argument("-C", "--calibration_dir", default="calibration_solutions",
        help="Directory with calibration solutions.")
    ps.add_argument("--solution_file", default=None)

    return ps.parse_args()


def get_stats(solutions, clip=1000):

    ao = fromfile(solutions)

    linear = np.asarray(ao[:, :, :, [0, 3]])
    linear.real[np.where(linear.real > clip)] = np.nan
    linear.imag[np.where(linear.imag > clip)] = np.nan

    amplitude = np.absolute(linear)
    phase = np.angle(linear)

    amplitude_xx = amplitude[:, :, :, 0]
    amplitude_yy = amplitude[:, :, :, 1]
    phase_xx = phase[:, :, :, 0]
    phase_yy = phase[:, :, :, 1]

    std_amp_xx = np.nanstd(amplitude_xx)
    std_amp_yy = np.nanstd(amplitude_yy)
    std_phase_xx = np.nanstd(phase_xx)
    std_phase_yy = np.nanstd(phase_yy)

    # std_real_xx = np.nanstd(linear[:, :, :, 0].real)
    # std_imag_xx = np.nanstd(linear[:, :, :, 0].imag)

    # std_real_yy = np.nanstd(linear[:, :, :, 1].real)
    # std_imag_yy = np.nanstd(linear[:, :, :, 1].imag)
    std = np.nanstd(linear)

    n_total = len(linear.flatten())
    n_nan = len(np.where(np.isnan(linear.flatten()))[0])
    perc_nan = n_nan / n_total

    # return std_real_xx, std_imag_xx, std_real_yy, std_imag_yy, perc_nan, std
    return std_amp_xx, std_phase_xx, std_amp_yy, std_phase_yy, perc_nan, std



def solutions_stats(obsids, solutions, std_cut_amp=50, std_cut_phase=2, perc_good=0.3, clip=1000.):

    good_solutions, good_obsids, stds = [], [], []

    for i in range(len(solutions)):

        try:
            std_amp_xx, std_phase_xx, std_amp_yy, std_phase_yy, perc_nan, std = get_stats(
                solutions[i], clip
            )
        except Exception:
            continue
            # raise

        if std_amp_xx > std_cut_amp:
            print(f"{solutions[i]} failing XX amp cut {std_amp_xx}")
        if std_amp_yy > std_cut_amp:
            print(f"{solutions[i]} failing YY amp cut {std_amp_yy}")
        if std_phase_xx > std_cut_phase:
            print(f"{solutions[i]} failing XX phase cut {std_phase_xx}")
        if std_phase_yy > std_cut_phase:
            print(f"{solutions[i]} failing YY phase cut {std_phase_yy}")
        if perc_nan > perc_good:
            print(f"{solutions[i]} nan cut {perc_nan}")
                
        if (std_amp_xx < std_cut_amp) and \
            (std_amp_yy < std_cut_amp) and \
            (std_phase_xx < std_cut_phase) and \
            (std_phase_yy < std_cut_phase) and \
            (perc_nan < perc_good):
            
            good_solutions.append(solutions[i])
            good_obsids.append(obsids[i])
            stds.append(std)


    return np.asarray(good_solutions), np.asarray(good_obsids), stds


def get_times(obsids):
    times = [int(obs) for obs in obsids]
    return np.asarray(times)


def check_single_solutions(obsid, 
    std_cut_amp=50,
    std_cut_phase=2, 
    perc_good=0.3, 
    solution_clip=1000,
    solution_sub="_solutions1.bin",
    calibration_dir=None,
    solution_file=None):

    if solution_file is None:
        if calibration_dir is None:
            solutions = "{0}/{0}{1}".format(obsid, solution_sub)
        else:
            solutions = "{2}/{0}{1}".format(obsid, solution_sub, calibration_dir)
    else:
        solutions = solution_file

    std_amp_xx, std_phase_xx, std_amp_yy, std_phase_yy, perc_nan, std = get_stats(
        solutions, solution_clip
    )

    if (std_amp_xx < std_cut_amp) and \
        (std_amp_yy < std_cut_amp) and \
        (std_phase_xx < std_cut_phase) and \
        (std_phase_yy < std_cut_phase) and \
        (perc_nan < perc_good):
        return solutions
    else:
        return None




def match_solutions(obsids, 
    std_cut_amp=50.,
    std_cut_phase=2.,
    perc_good=0.3,
    solution_clip=1000.,
    solution_sub="_solutions1.bin",
    calibration_dir=None):

    if calibration_dir is None:
        solutions = np.asarray([
            "{0}/{0}{1}".format(obsid, solution_sub) for obsid in obsids
        ])
    else:
        solutions = np.asarray([
            "{2}/{0}{1}".format(obsid, solution_sub, calibration_dir) for obsid in obsids
        ])

    good_solutions, good_times, stds = solutions_stats(
        obsids=obsids,
        solutions=solutions, 
        std_cut_amp=std_cut_amp,
        std_cut_phase=std_cut_phase, 
        perc_good=perc_good,
        clip=solution_clip
    )
    
    times = get_times(obsids)

    assigned_solutions = []
    assigned_calids = []

    for i in range(len(times)):
        
        idx = (np.abs(good_times - times[i])).argmin()
        assigned_solutions.append(good_solutions[idx])
        assigned_calids.append(good_times[idx])

    return np.asarray(assigned_solutions), np.asarray(assigned_calids), np.asarray(stds)


def writeout_string(calid):

    calid_str = " ".join(
        [str(cal) for cal in calid]
    )

    print(calid_str)

def writeout_textfile(outname, obsids, assigned_solutions, calid, stds):

    obsids = np.asarray(obsids).astype(int)
    diff = np.abs(calid - obsids)

    print("Unique solutions: {}".format(set(calid)))
    print("Max time separation: {} hours".format(
        np.max(diff)/3600.  # hours
    ))

    best_sol = np.argmin(stds)
    print("Best solution: {}".format(assigned_solutions[best_sol]))

    with open(outname, "w+") as f:
        for i in range(len(obsids)):
            f.write("{} {} {}\n".format(obsids[i], calid[i], diff[i]/3600.))
    


def cli(args):

    if len(args.obsids) > 1:
        assigned_solutions, assigned_calids, stds = match_solutions(
            obsids=args.obsids,
            std_cut_amp=args.amp_cut,
            std_cut_phase=args.phase_cut,
            perc_good=args.perc_nan,
            solution_sub=args.solution_stub,
            solution_clip=args.clip,
            calibration_dir=args.calibration_dir
        )

        if args.outname is not None:
            writeout_textfile(
                outname=args.outname,
                obsids=args.obsids,
                assigned_solutions=assigned_solutions,
                calid=assigned_calids,
                stds=stds
            )
            
        else:
            writeout_string(assigned_calids)
    
    else:
        assigned_solutions = check_single_solutions(
            obsid=args.obsids[0],
            std_cut_amp=args.amp_cut,
            std_cut_phase=args.phase_cut,
            perc_good=args.perc_nan,
            solution_sub=args.solution_stub,
            solution_clip=args.clip,
            calibration_dir=args.calibration_dir,
            solution_file=args.solution_file
        )
        if assigned_solutions is not None:
            print(assigned_solutions)


if __name__ == "__main__":
    cli(get_args())

    
