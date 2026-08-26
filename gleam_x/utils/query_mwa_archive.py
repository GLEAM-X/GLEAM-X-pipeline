import urllib
import json
import importlib
from argparse import ArgumentParser, ArgumentTypeError
import logging
from typing import Iterable, Dict, Any, Optional
from astropy.coordinates import Angle
from astropy.units import hourangle, deg

def get_rich_log_handler():
    """Return rich.logging.RichHandler when available, otherwise None."""
    try:
        return importlib.import_module("rich.logging").RichHandler
    except ImportError:
        return None

def get_rich_progress():
    """Return rich.progress.Progress when available, otherwise None."""
    try:
        return importlib.import_module("rich.progress").Progress
    except ImportError:
        return None

def configure_logging() -> None:
    """Configure colorized logging when rich is available."""
    rich_handler = get_rich_log_handler()

    if rich_handler is not None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            handlers=[
                rich_handler(
                    rich_tracebacks=True,
                    show_path=False,
                    show_time=True,
                    markup=True)])
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="# %(module)s # %(lineno)d # %(levelname)s # %(message)s")

configure_logging()
logger = logging.getLogger("Query MWA Archive")
logger.setLevel(logging.INFO)

BASEURL = "http://ws.mwatelescope.org/"

def hms_to_deg(hms: str) -> float:
    """Convert a string in the format 'HH:MM:SS' to degrees

    Args:
        hms (str): String in the format 'HH:MM:SS'

    Returns:
        float: The equivalent value in degrees
    """
    try:
        return Angle(hms, unit=hourangle).degree
    except ValueError as err:
        logger.error(f"Invalid HMS format for RA: {hms}. Expected format is 'HH:MM:SS'. Error details: {err}")
        raise err

def dms_to_deg(dms: str) -> float:
    """Convert a string in the format 'DD:MM:SS' to degrees

    Args:
        dms (str): String in the format 'DD:MM:SS'

    Returns:
        float: The equivalent value in degrees
    """
    try:
        return Angle(dms, unit=deg).degree
    except ValueError as err:
        logger.error(f"Invalid DMS format for Dec: {dms}. Expected format is 'DD:MM:SS'. Error details: {err}")
        raise err

def parse_ra(value: str) -> float:
    """Parse RA as degrees or HH:MM:SS and return degrees."""
    try:
        return float(value)
    except ValueError:
        try:
            return hms_to_deg(value)
        except ValueError as err:
            raise ArgumentTypeError(
                f"Invalid --minra/--maxra value '{value}'. Use degrees or 'HH:MM:SS'."
            ) from err

def parse_dec(value: str) -> float:
    """Parse Dec as degrees or DD:MM:SS and return degrees."""
    try:
        return float(value)
    except ValueError:
        try:
            return dms_to_deg(value)
        except ValueError as err:
            raise ArgumentTypeError(
                f"Invalid --mindec/--maxdec value '{value}'. Use degrees or 'DD:MM:SS'."
            ) from err

def getmeta(servicetype: str='metadata', service: str='find', params: Dict[Any, Any]=None) -> Dict[Any, Any]:
    """Given a JSON web servicetype ('observation' or 'metadata'), a service name (eg 'obs', find, or 'con')
       and a set of parameters as a Python dictionary, return a Python dictionary containing the result.

    Args:
        servicetype (str, optional): Desired webservice data return. Defaults to 'metadata'.
        service (str, optional): Desired webservice end point to query. Defaults to 'find'.
        params (Dict[Any, Any], optional): Additional parameters to pass to webservice. Defaults to None.

    Returns:
        Dict[Any, Any]: Returned data structure from the webservice
    """
    
    if params:
        # Turn the dictionary into a string with encoded 'name=value' pairs
        data = urllib.parse.urlencode(params)
    else:
        data = ''

    # Get the data
    try:
        result = json.load(urllib.request.urlopen(BASEURL + servicetype + '/' + service + '?' + data))
    except urllib.error.HTTPError as err:
        logging.error("HTTP error from server: code=%d, response:\n %s" % (err.code, err.read()))
        raise err
    except urllib.error.URLError as err:
        logging.error("URL or network error: %s" % err.reason)
        raise err

    # Return the result dictionary
    return result

def query_archive(
    minra: float,
    maxra: float,
    mindec: float,
    maxdec: float,
    maxsunel: float = 0.0,
    mode: str = 'MWAX_CORRELATOR',
    contigfreq: int = 1,
    int_time: float = None,
    freq_res: float = None,
    project_id: Optional[str] = None,
    cent_chan: Optional[int] = None
) -> Iterable[int]:
    """Query the MWA data archive to obtain a list of obsids to process based on the search criteria.

    Args:
        minra (float): Minimum right ascension (in degrees) of the observations to search for.
        maxra (float): Maximum right ascension (in degrees) of the observations to search for.
        mindec (float): Minimum declination (in degrees) of the observations to search for.
        maxdec (float): Maximum declination (in degrees) of the observations to search for.
        maxsunel (float): Maximum solar elevation (in degrees) of the observations to search for. Defaults to 0.0 (ie only return observations that are below the horizon).
        mode (str): Observation mode to search for.  Defaults to 'MWAX_CORRELATOR'.
        contigfreq (int): Whether to only return observations with contiguous frequency coverage (1) or not (0). Defaults to 1.
        int_time (float): Integration time (in seconds) to search for. Defaults to None.
        freq_res (float): Frequency resolution (in kHz) to search for. Defaults to None.
        project_id (str, optional): Project code associated with the desired observations. Defaults to None.
        cent_chan (int, optional): Only return the observations at the specified central frequecy. If None no specification is required. Defaults to None.

    Returns:
        Iterable[int]: set of obsids to process
    """
    obs_id_list = []
    
    # Available options are described at
    # https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24969492/Observation+metadata+web+services
    meta_params = {
            'minra': minra,
            'maxra': maxra,
            'mindec': mindec,
            'maxdec': maxdec,
            'maxsunel': maxsunel,
            'mode': mode,
            'contigfreq': contigfreq,
            'notdeleted': 'on',
            'dataquality': 1,
            'int_time': int_time if int_time is not None else '',
            'freq_res': freq_res if freq_res is not None else '',
            'projectid': (project_id if project_id is not None else ''),
            'cenchan': (cent_chan if cent_chan is not None else ''),
            'dict': 1,
            'nocache': 1
    }

    obs_list = getmeta(service='find', params=meta_params)

    if obs_list is not None:
        rich_progress = get_rich_progress()

        if rich_progress is not None:
            with rich_progress(transient=True) as progress:
                task_id = progress.add_task("Checking ASVO data readiness", total=len(obs_list))

                for obs in obs_list:
                    if obs['mwas.projectid'][0] != 'C':
                        obs_id = obs['mwas.starttime']
                        if logger.isEnabledFor(logging.DEBUG):
                            progress.console.log(f"Checking {obs_id=}")

                        # Confirm that ASVO is ready to hand out the data
                        obs_ready = getmeta(service='data_ready', params={'obs_id':obs['mwas.starttime']})

                        if obs_ready["dataready"] is True:
                            if logger.isEnabledFor(logging.DEBUG):
                                progress.console.log(f"Data ready {obs_id=} appending")
                            obs_id_list.append(obs_id)
                        elif logger.isEnabledFor(logging.DEBUG):
                            progress.console.log(f"Data for {obs_id=} is not ready")

                    progress.advance(task_id)
        else:
            for obs in obs_list:
                if obs['mwas.projectid'][0] != 'C':
                    obs_id = obs['mwas.starttime']
                    logger.debug(f"Checking {obs_id=}")

                    # Confirm that ASVO is ready to hand out the data
                    obs_ready = getmeta(service='data_ready', params={'obs_id':obs['mwas.starttime']})

                    if obs_ready["dataready"] is True:
                        logger.debug(f"Data ready {obs_id=} appending")
                        obs_id_list.append(obs_id)
                    else:
                        logger.debug(f"Data for {obs_id=} is not ready")
        
    logger.debug(f"Returning {obs_id_list=}")
    return obs_id_list

if __name__ == "__main__":
    parser = ArgumentParser(epilog="Visit https://ws.mwatelescope.org/metadata/find and https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24969492/Observation+metadata+web+services for more details on search options and their acceptable values.")
    parser.add_argument("-lr", "--minra", dest='minra', type=parse_ra, required=True,
                        help="Minimum right ascension to search for (format: 'HH:MM:SS' or in degrees)")
    parser.add_argument("-ur", "--maxra", dest='maxra', type=parse_ra, required=True,
                        help="Maximum right ascension to search for (format: 'HH:MM:SS' or in degrees)")
    parser.add_argument("-ld", "--mindec", dest='mindec', type=parse_dec, required=True,
                        help="Minimum declination to search for (format: 'DD:MM:SS' or in degrees)")
    parser.add_argument("-ud", "--maxdec", dest='maxdec', type=parse_dec, required=True,
                        help="Maximum declination to search for (format: 'DD:MM:SS' or in degrees)")
    parser.add_argument("-s", "--maxsunel", dest='maxsunel', type=float, default=0.0,
                        help="Maximum elevation of the sun (in degrees) at the mid-time of the observation. Defaults to 0.0.")
    parser.add_argument("-m", "--mode", dest='mode', type=str, default='MWAX_CORRELATOR',
                        help="Observation mode to search for (eg: 'HW_LFILES', 'MWAX_BEAMFORMER', 'MWAX_VCS'). Defaults to MWAX_CORRELATOR.")
    parser.add_argument("-c", "--contigfreq", dest='contigfreq', type=int, default=1,
                        help="Whether to only return observations with contiguous frequency coverage (1) or not (0). Defaults to 1.")
    parser.add_argument("-i", "--int-time", dest='int_time', type=float, default=None,
                        help="Integration time (in seconds) to search for (default = None)")
    parser.add_argument("-f", "--freq-res", dest='freq_res', type=float, default=None,
                        help="Frequency resolution (in kHz) to search for (default = None)")
    parser.add_argument("-p", "--project-id", dest='project_id', type=str, default=None,
                        help="MWA observing project (default = None)")
    parser.add_argument("-o", "--output", dest='output', type=str, default=None,
                        help="Output text file for search args (Defaults to None)")
    parser.add_argument("-ch", "--cent-chan", default=None, type=int,
                        help="Limit search to the specified central channel. Defaults to None.")
    parser.add_argument("-v", "--verbose", default=False, action="store_true",
                        help="Enable debug logging. Disabled by default.")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    obs_id_list = query_archive(
        args.minra, args.maxra, args.mindec, args.maxdec,
        maxsunel = args.maxsunel,
        mode = args.mode,
        contigfreq = args.contigfreq,
        int_time = args.int_time,
        freq_res = args.freq_res,
        project_id = args.project_id,
        cent_chan = args.cent_chan,
    )

    if obs_id_list is False:
        logger.error(f"Failed to find any matching observations. Please check your search criteria and try again.")
    else:
        if args.output is not None:
            logger.info(f"Writing {len(obs_id_list)} obsids to {args.output}.")
            with open(args.output, "w") as f:
                for obs_id in obs_id_list:
                    f.write(f"{obs_id}\n")

        logger.debug(f"Found observations: {obs_id_list}")
