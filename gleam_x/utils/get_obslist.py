#!/usr/bin/env python

import pyvo as vo
from argparse import ArgumentParser

mwa_tap_service = vo.dal.TAPService("http://vo.mwatelescope.org/mwa_asvo/tap")

def get_obsids(date,calibration,chan=None):

    if chan is not None: 
        results = mwa_tap_service.search(f"SELECT obs_id FROM mwa.observation WHERE projectid='G0008' AND starttime_utc >= '{date} 00:00:00' AND stoptime_utc < '{date} 23:59:59' AND dataqualityname = 'Good' AND center_channel_number = {chan} AND calibration='{calibration}'")
    else:
        results = mwa_tap_service.search(f"SELECT obs_id FROM mwa.observation WHERE projectid='G0008' AND starttime_utc >= '{date} 00:00:00' AND stoptime_utc < '{date} 23:59:59' AND dataqualityname = 'Good' AND calibration='{calibration}'")

    return results.to_table() 

def create_obsids_txt(df, out):
    df.write(out, format="ascii.no_header",overwrite=True)
    return 

if __name__ == "__main__":
    parser = ArgumentParser(
        description="Pulls down a list of `obs_ids` provide a set of specifications"
    )
    parser.add_argument(
        "-d",
        "--date",
        default=None,
        type=str,
        help="Obsids only on this specific date ar ereturned, date is expected YYYY-MM-DD",
    )
    parser.add_argument(
        '-c',
        '--chan',
        default=None,
        type=int,
        choices=[68, 92, 120, 144, 168],
        help="Central channel, note for GLEAM bands central are 1 less than you think (68, 92, 120, 144, 168 )"
    )
    parser.add_argument(
        '-o',
        '--out',
        default=None,
        type=str,
        help="Out filename, text string assumed"
    )
    parser.add_argument(
        '--calibration',
        default="No",
        type=str,
        choices=["Yes", "No"],
        help="Do you wish to include the calibration observations? (Yes, No)"
    )
    
    args = parser.parse_args()
    print(args)
    
    df = get_obsids(
        date=args.date,
        calibration=args.calibration,
        chan=args.chan
    )

    print(f"Found {len(df)} obsids!")

    if args.out is not None:
        create_obsids_txt(df, args.out)
        

