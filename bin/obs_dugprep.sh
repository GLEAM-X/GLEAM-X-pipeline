#! /bin/bash

# -----------------------------------------------------------------------------
# INFO AND SETUP 
# -----------------------------------------------------------------------------

usage()
{
echo "obs_dugprep.sh [-t test] -p project -a acacia obslist
  -p project : project, no default
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  -a acacia  : acacia bucket name to draw obsids from 
  obsnum  : the obsid to process, or a text file of obsids (newline 
               separated)." 1>&2;
exit 1;
}

#initial variables
project=
tst=
acacia=
# parse args and set options
while getopts ':ta:p:' OPTION
do
    case "$OPTION" in
    a)
        acacia=${OPTARG}
        ;;
    p)
        project=${OPTARG}
        ;;
    t)
        tst=1
        ;;
    ? | : | h)
        usage
        ;;
  esac
done
# set the obsid to be the first non option
shift  "$(($OPTIND -1))"
obslist=$1

# if obsid is empty then just print help

if [[ -z ${obslist} ]] || [[ -z $project ]] 
then
    usage
fi

# queue="-p ${GXSTANDARDQ}"
base="${GXSCRATCH}/$project"
# code="${GXBASE}"


script="${GXSCRIPT}/dugprep_${obslist}.sh"
cat "${GXBASE}/templates/dugprep.tmpl" | sed -e "s:OBSLIST:${obslist}:g" \
                                 -e "s:BASEDIR:${base}:g" \
                                 -e "s:BUCKET:${acacia}:g" > "${script}"

chmod 755 "${script}"

if [[ ! -z ${tst} ]]
then
    echo "script is ${script}"
    echo "submit via:"
    echo "./${script} | tee ${GXBASE}/log_${GXCLUSTER}/${script}.log"
    exit 0
fi

source ${script} | tee ${script}.log