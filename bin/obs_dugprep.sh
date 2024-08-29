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
timeres=
freqres=
edgeflag=80
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

if [[ -z ${acacia} ]]
then 
    asvo_flag=1
fi

# queue="-p ${GXSTANDARDQ}"
base="${GXSCRATCH}/$project"
cd "${base}" 
# code="${GXBASE}"

if [[ -f "${obslist}" ]]
then 
    list=$(cat "${obslist}")
else
    list=(${obslist})
fi 


for obsnum in $list
do
    # Note this implicitly 
    if [[ $obsnum -lt 1151402936 ]] ; then
        telescope="MWA128T"
        basescale=1.1
        if [[ -z $freqres ]] ; then freqres=40 ; fi
        if [[ -z $timeres ]] ; then timeres=4 ; fi
    elif [[ $obsnum -ge 1151402936 ]] && [[ $obsnum -lt 1191580576 ]] ; then
        telescope="MWAHEX"
        basescale=2.0
        if [[ -z $freqres ]] ; then freqres=40 ; fi
        if [[ -z $timeres ]] ; then timeres=8 ; fi
    elif [[ $obsnum -ge 1191580576 ]] ; then
        telescope="MWALB"
        basescale=0.5
        if [[ -z $freqres ]] ; then freqres=40 ; fi
        if [[ -z $timeres ]] ; then timeres=4 ; fi
    fi
done 


script="${GXSCRIPT}/dugprep_${obslist}.sh"
cat "${GXBASE}/templates/dugprep.tmpl" | sed -e "s:OBSLIST:${obslist}:g" \
                                 -e "s:BASEDIR:${base}:g" \
                                 -e "s:ASVOFLAG:${asvo_flag}:g" \
                                 -e "s:TRES:${timeres}:g" \
                                 -e "s:FRES:${freqres}:g" \
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