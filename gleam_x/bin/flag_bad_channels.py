from argparse import ArgumentParser
from pathlib import Path
from shutil import copy2
from matplotlib import pyplot as plt
import numpy as np
from calplots import aocal
import logging

def setFonts(fontsize=12, axisLW=1, ticksize=5, tick_direction='out', padding=5, top_ticks=False, right_ticks=False):
	plt.rc('font', family='serif', size=fontsize)													# controls default font family and text sizes
	plt.rc('axes', titlesize=fontsize, linewidth=axisLW, labelsize=fontsize, labelpad=padding)		# fontsize of the axes title and the x and y labels
	plt.rc('xtick', labelsize=fontsize, direction=tick_direction, top=top_ticks)					# fontsize of the xtick labels
	plt.rc('ytick', labelsize=fontsize, direction=tick_direction, right=right_ticks)				# fontsize of the ytick labels
	plt.rc('xtick.major', pad=padding, width=axisLW, size=ticksize)									# size of x major ticks
	plt.rc('ytick.major', pad=padding, width=axisLW, size=ticksize)									# size of y major ticks
	plt.rc('xtick.minor', width=axisLW, size=ticksize/2)											# size of x minor ticks
	plt.rc('ytick.minor', width=axisLW, size=ticksize/2)											# size of y minor ticks
	plt.rc('legend', fontsize=fontsize)    															# legend fontsize
	plt.rc('figure', titlesize=fontsize)															# fontsize of the figure title
	plt.rc('mathtext', fontset='custom', rm='serif', it='serif:italic', bf='serif:bold', cal='serif')

setFonts()

def configure_logger(name: str = "flag_bad_channels", level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        # Format: [2024-06-01 12:00:00] [INFO] Message
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger

def plot_cal_solution(mean_amps, amp_m=None, amp_s=None, threshold=1, hline_label="", fill_label="", title="", ylabel="Mean Gain Amplitude", xlabel="Channel", figsize=(18, 6), fig_path=""):
    plt.figure(figsize=figsize)
    plt.plot(mean_amps, color="blue", label="Mean Gain Amplitudes")

    # Plot the mean gain amplitude with a horizontal line and shaded region for ±1 standard deviation
    if amp_m is not None:
        plt.axhline(amp_m, color="blue", linestyle="--", label=hline_label)
    if amp_s is not None:
        plt.fill_between(range(len(mean_amps)), amp_m - threshold * amp_s, amp_m + threshold * amp_s, color="blue", alpha=0.2, label=fill_label)

    plt.grid()
    plt.legend()
    plt.xlim(0, len(mean_amps))
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.savefig(fig_path, bbox_inches='tight')
    plt.close()

POLS = {pol: i for i, pol in enumerate(['XX', 'XY', 'YX', 'YY'])}

def flag_bad_channels(cal_sol_file: Path, sigma_threshold: float = 3.0, mad_threshold: float = 2.0, niter: int = 2, pols: list[str] = ['XY', 'YX'], diagnosis: bool = True, verbose: bool = False):
    logger = configure_logger()
    if verbose:
        logger.setLevel(logging.DEBUG)
    logger.info(f"Processing calibration solution file: {cal_sol_file}")

    bad_channels = []

    # Load the calibration solution file and infer bad channels. If multiple files are provided, we will only use the first one to infer bad channels and apply the same flagging to all files.
    ao = aocal.fromfile(cal_sol_file) # shape: (n_int, n_ant, n_chan, n_pol), i.e., (time integrations, antennas, frequency channels, polarizations)
    logger.debug(f"Loaded calibration solution file with shape: {ao.shape}")

    ############################## Handling band gaps ##############################
    # Replace nan values with zeros and compute mean gain amplitudes across antennas and polarizations for each channel.
    mean_amps = np.mean(np.nan_to_num(np.abs(ao[..., [POLS[pol] for pol in pols]])), axis=(0, 1, 3))  # shape: (n_chan,)
    band_gaps = np.where(mean_amps == 0) # Identify band gaps where mean amplitude is zero (after replacing NaNs with zeros)

    amp_m, amp_s = np.mean(mean_amps), np.std(mean_amps) # Initial global mean and std
    mean_amps[band_gaps] = amp_m # Replace band gaps with the global mean to avoid skewing the outlier detection
    amp_m, amp_s = np.mean(mean_amps), np.std(mean_amps) # Recompute mean and std after replacing band gaps
    mean_amps[band_gaps] = amp_m

    if diagnosis:
        plot_cal_solution(mean_amps, amp_m=amp_m, amp_s=amp_s, threshold=sigma_threshold, hline_label=f"Global Mean: {amp_m:.3f}", fill_label=fr"±{sigma_threshold} $\sigma$ of Std: {amp_s:.3f}", title="Before Flagging; Pols: " + ", ".join(pols), fig_path=f"{cal_sol_file.with_name(cal_sol_file.stem + '_1_before_flagging.png')}")

    ############################## Flagging bad coarse channels based on median and MAD of binned mean amplitudes ##############################
    binned_mean_amps = np.array(mean_amps).reshape(-1, 16).mean(axis=1) # Bin the mean amplitudes into groups of 16 channels and compute the average for each bin
    median_amp = np.median(binned_mean_amps)
    mad_amp = np.median(np.abs(binned_mean_amps - median_amp))
    if diagnosis:
        plot_cal_solution(binned_mean_amps, amp_m=median_amp, amp_s=mad_amp, threshold=mad_threshold, hline_label=f"Global Median: {median_amp:.3f}", fill_label=fr"±{mad_threshold} $\sigma$ of MAD: {mad_amp:.3f}", title="Binned Coarse Channel Amplitudes; Pols: " + ", ".join(pols), xlabel="Coarse Channel", fig_path=f"{cal_sol_file.with_name(cal_sol_file.stem + '_2_coarse_channels_before_flagging.png')}")
    bad_coarse_channels = np.where(binned_mean_amps - median_amp > mad_threshold * mad_amp)[0] # FLag coarse channels whose binned mean amplitude is greater than median + mad_threshold * MAD or less than median - mad_threshold * MAD
    logger.info(f"Identified {len(bad_coarse_channels)} bad coarse channels based on median and MAD: {bad_coarse_channels}")

    for coarse_ch in bad_coarse_channels:
        bad_channels.extend(range(coarse_ch * 16, (coarse_ch + 1) * 16)) # Flag all fine channels corresponding to the bad coarse channels
    logger.info(f"Total bad channels after including fine channels corresponding to bad coarse channels: {len(bad_channels)}")

    mean_amps[bad_channels] = median_amp # Flag the bad channels by setting their mean amplitudes to the global mean
    mean_amps[band_gaps] = median_amp

    amp_m, amp_s = np.mean(mean_amps), np.std(mean_amps) # Recompute mean and std after coarse channel flagging
    mean_amps[bad_channels] = amp_m # Since flagging will change the mean amplitudes, set them to the global mean once again for the next iteration
    mean_amps[band_gaps] = amp_m
    if diagnosis:
        plot_cal_solution(mean_amps, amp_m=amp_m, amp_s=amp_s, threshold=sigma_threshold, hline_label=f"Global Mean: {amp_m:.3f}", fill_label=fr"±{sigma_threshold} $\sigma$ of Std: {amp_s:.3f}", title=f"After Coarse Channel Flagging; Pols: " + ", ".join(pols), ylabel="Mean Gain Amplitudes", fig_path=f"{cal_sol_file.with_name(cal_sol_file.stem + '_3_after_coarse_channel_flagging.png')}")

    ############################## Bandpass equalization ##############################
    binned_mean_amps = np.median(np.array(mean_amps).reshape(-1, 32), axis=1) # Re-bin the mean amplitudes after coarse channel flagging for band equalization before the iterative flagging of fine channels
    for i in range(len(binned_mean_amps)):
        mean_amps[i*32:(i+1)*32] -= binned_mean_amps[i] # Set the mean amplitudes of the fine channels in each bin to the binned mean amplitude to equalize the bandpass before iterative flagging

    mean_amps[bad_channels] = 0
    mean_amps[band_gaps] = 0
    amp_s = np.std(mean_amps) # Recompute std after bandpass equalization since it will change the distribution of mean amplitudes
    if diagnosis:
        plot_cal_solution(mean_amps, amp_m=0, amp_s=amp_s, threshold=sigma_threshold, hline_label=f"Global Mean: {0:.3f}", fill_label=fr"±{sigma_threshold} $\sigma$ of Std: {amp_s:.3f}", title=f"Bandpass Equalized Mean Amplitudes; Pols: " + ", ".join(pols), ylabel="Bandpass Equalized Mean Gain Amplitudes", fig_path=f"{cal_sol_file.with_name(cal_sol_file.stem + '_4_bandpass_equalized_before_iterative_flagging.png')}")

    ############################## Iterative flagging of fine channels based on mean amplitude outliers ##############################
    for iter in range(niter):
        logger.debug(f"Iter {iter + 1}: std = {amp_s:.3f}")

        bad_channels += np.where(mean_amps > sigma_threshold * amp_s)[0].tolist() # Flag channels with mean amplitude greater than mean + sigma_threshold * std
        logger.info(f"Iteration {iter + 1}: Found total {len(bad_channels)} bad channels: {bad_channels}")

        mean_amps[bad_channels] = 0 # Set mean amplitudes of flagged channels to 0 for the next iteration

        amp_s = np.std(mean_amps) # Recompute mean and std after each iteration of flagging
        if diagnosis:
            plot_cal_solution(mean_amps, amp_m=0, amp_s=amp_s, threshold=sigma_threshold, hline_label=f"Global Mean: {0:.3f}", fill_label=fr"±{sigma_threshold} $\sigma$ of Std: {amp_s:.3f}", title=f"After Iteration {iter + 1}; Pols: " + ", ".join(pols), fig_path=f"{cal_sol_file.with_name(cal_sol_file.stem + f'_{5 + iter}_after_iteration_{iter + 1}.png')}")

    logger.info(f"Identified a total of {len(bad_channels)} bad channels from {cal_sol_file} file.")
    return bad_channels

if __name__ == "__main__":
    parser = ArgumentParser(description="Flag bad channels in a calibration solution file using iterative outlier rejection on mean gain amplitudes.")
    parser.add_argument("cal_sol_files", nargs='+', type=Path, help="Path to the calibration solution files (binary format). An ASCII file containing the list of calibration solution files can also be provided.")
    parser.add_argument("-s", "--sigma_threshold", type=float, default=3.0, help="Sigma threshold for flagging bad channels (default: 3.0).")
    parser.add_argument("-m", "--mad_threshold", type=float, default=3.0, help="Median Absolute Deviation (MAD) threshold for flagging bad coarse channels (default: 2.0).")
    parser.add_argument("-n", "--niter", type=int, default=2, help="Number of iterations for outlier rejection (default: 2).")
    parser.add_argument("-p", "--pols", nargs='+', type=str, default=['XY', 'YX'], help="List of polarization indices to use for flagging (default: ['XY', 'YX'] since RFI is almost always linearly polarised).")
    parser.add_argument("-b", "--backup", action="store_true", help="Create a backup of the original calibration solution file(s) before flagging and overwrite them.")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Path to save the flagged calibration solution file (if not provided, will save with '_flagged' suffix).")
    parser.add_argument("-d", "--diagnosis", action="store_false", help="Disable generation of diagnostic plots for the flagging process.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging and debug plots.")
    args = parser.parse_args()

    logger = configure_logger()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        with open(args.cal_sol_files[0]) as f:
            cal_sol_files: list[Path] = [Path(line.strip()).resolve() for line in f]
    except (UnicodeDecodeError or FileNotFoundError):
        cal_sol_files: list[Path] = [file.resolve() for file in args.cal_sol_files]

    # Remove all files that end with "_flagged.bin" or "_backup.bin" or "_failed.bin" from the list of calibration solution files to process since they have already been flagged or are backups or failed files.
    cal_sol_files = [f for f in cal_sol_files if not (f.name.endswith("_flagged.bin") or f.name.endswith("_backup.bin") or f.name.endswith("_failed.bin"))]
    if len(cal_sol_files) == 0:
        logger.error("No calibration solution files to process. All provided files are either flagged or backups.")
        exit(0)
    logger.debug(f"Removed {len(args.cal_sol_files) - len(cal_sol_files)} files that are already flagged or are backup files.")
    logger.info("Starting bad channel flagging process.")

    all_bad_channels = []

    for cal_sol_file in cal_sol_files:
        all_bad_channels.extend(flag_bad_channels(cal_sol_file, sigma_threshold=args.sigma_threshold, mad_threshold=args.mad_threshold, niter=args.niter, pols=args.pols, diagnosis=args.diagnosis, verbose=args.verbose))
    
    all_bad_channels = np.unique(all_bad_channels).tolist() # Get the unique bad channels across all files

    for cal_sol_file in cal_sol_files:
        ao = aocal.fromfile(cal_sol_file) # shape: (n_int, n_ant, n_chan, n_pol)
        ao[..., all_bad_channels, :] = 0 # Set the gains of the bad channels to zero in the original calibration solution.
        # Visibilities will be flagged when you apply these solutions to the data since the gains will be zero.

        if args.backup:
            backup_file = cal_sol_file.with_name(cal_sol_file.stem + "_backup.bin")
            logger.info(f"Backup created: {copy2(cal_sol_file, backup_file)}")
            output_file = cal_sol_file
        else:
            output_file = args.output if args.output is not None else cal_sol_file.with_name(cal_sol_file.stem + "_flagged.bin")
        ao.tofile(output_file)
        logger.info(f"Flagged calibration solution saved to: {output_file}")

        # figsize = (18, 6)
        # obsid = 1062015584
        # amp_fig = plt.figure(figsize=figsize)
        # amp_ax = amp_fig.add_subplot(111)

        # for timestep in range(ao.n_int):
        #     for pol in range(ao.n_pol):
        #         for ant in range(ao.n_ant):
        #             amp_ax.plot(np.abs(ao[timestep, ant, :, pol]))

        # amp_ax.grid()
        # amp_ax.set_xlabel("Channel")
        # amp_ax.set_ylabel("Gain Amplitude")
        # amp_ax.set_title("Gains of All Antennas and All Polarizations After Flagging")
        # amp_fig.tight_layout()
        # amp_fig.savefig(f"{obsid}_gain_amplitude_flagged.png")