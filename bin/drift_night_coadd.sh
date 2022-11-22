#! /bin/bash

usage()
{
echo "drift_night_coadd.sh [-p project] [-d dep] [-q queue] [-a account] [-t] [-r ra] [-e dec] list_of_nights.txt

Task to combine mosaics that have been produced by 'drift_mosaic.sh' into a single, larger image. The contents of
list_of_nights should be directed to the adopted mosaic folder for each nigh, incase a non-default 'mosaic' folder
name was used.

  -p project  : project, (must be specified, no default)
  -d dep     : job number for dependency (afterok)
  -t          : test. Don't submit job, just make the batch file
                and then return the submission command
  -r RA       : Right Ascension (decimal hours; default = guess from observation list)
  -e dec      : Declination (decimal degrees; default = guess from observation list)
  -m mosaicdir: Directory name for mosaics to be created (default = mosaics) 
  nightlist  : the list of nights with existing coadded images to process" 1>&2;
exit 1;
}

pipeuser=$(whoami)

#initial variables
dep=
queue="-p ${GXSTANDARDQ}"
tst=
ra=
dec=
mosaicdir=

# parse args and set options
while getopts ':td:p:o:r:e:m:' OPTION
do
    case "$OPTION" in
    d)
        dep=${OPTARG} ;;
    p)
        project=${OPTARG} ;;
	o)
	    obslist=${OPTARG} ;;
    r)
        ra=${OPTARG} ;;
    e)
        dec=${OPTARG} ;;
    m) 
        mosaicdir=${OPTARG} ;;
    t)
        tst=1 ;;
    ? | : | h)
            usage ;;
  esac
done
# set the nightlist to be the first non option
shift  "$(($OPTIND -1))"
nightlist=$1

# if obslist is not specified or an empty file then just print help

if [[ -z ${nightlist} ]] || [[ ! -s ${nightlist} ]] || [[ ! -e ${nightlist} ]] || [[ -z $project ]]
then
    usage
fi

if [[ ! -z ${dep} ]]
then
    depend="--dependency=afterok:${dep}"
fi

if [[ ! -z ${GXACCOUNT} ]]
then
    account="--account=${GXACCOUNT}"
fi

queue="-p ${GXSTANDARDQ}"
base="${GXSCRATCH}/${project}"

obss=($(sort "${nightlist}"))
listbase=$(basename "${nightlist}")
listbase=${listbase%%.*}
script="${GXSCRIPT}/nightcoadd_${listbase}.sh"

cat "${GXBASE}/templates/nightcoadd.tmpl" | sed -e "s:NIGHTLIST:${nightlist}:g" \
                                      -e "s:RAPOINT:${ra}:g" \
                                      -e "s:DECPOINT:${dec}:g" \
                                      -e "s:BASEDIR:${base}:g" \
                                      -e "s:MOSAICDIR:${mosaicdir}:g" \
                                      -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

output="${GXLOG}/nightcoadd_${listbase}.o%A_%a"
error="${GXLOG}/nightcoadd_${listbase}.e%A_%a"

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > "${script}.sbatch"
echo "srun ${GXSRUNLINE} singularity run ${GXCONTAINER} ${script}" >> ${script}.sbatch

# Automatically runs a job array for each sub-band
sub="sbatch  --begin=now+5minutes --array=0-24  --export=ALL  --time=20:00:00 --mem=${GXABSMEMORY}G -M ${GXCOMPUTER} --output=${output} --error=${error}"
sub="${sub} ${GXNCPULINE} ${account} ${GXTASKLINE} ${depend} ${queue} ${script}.sbatch"
if [[ ! -z ${tst} ]]
then
    echo "script is ${script}"
    echo "submit via:"
    echo "${sub}"
    exit 0
fi

# submit job
jobid=($(${sub}))
jobid=${jobid[3]}

# rename the err/output files as we now know the jobid
error=${error//%A/"${jobid}"}
output=${output//%A/"${jobid}"}

freqs=(072-080MHz 072-103MHz 080-088MHz 088-095MHz 095-103MHz 103-111MHz 103-134MHz 111-118MHz
118-126MHz 126-134MHz 139-147MHz 139-170MHz 147-154MHz 154-162MHz 162-170MHz 170-177MHz
170-200MHz 177-185MHz 185-193MHz 193-200MHz 200-208MHz 200-231MHz 208-216MHz 216-223MHz
223-231MHz)
echo "Submitted ${script} as ${jobid} . Follow progress here:"

# record submission
for taskid in $(seq 0 1 24)
do
    terror="${error//%a/${taskid}}"
    toutput="${output//%a/${taskid}}"
    freq=${freqs[$taskid]}

    echo "${toutput}"
    echo "${terror}"

    # if [ "${GXTRACK}" = "track" ] 
    # then
    #     ${GXCONTAINER} track_task.py queue_mosaic --jobid="${jobid}" --taskid="${taskid}" --task='mosaic' --submission_time="$(date +%s)" --batch_file="${script}" \
    #                             --batch_obs_id "${obss[@]}" --stderr="${terror}" --stdout="${toutput}" \
    #                             --subband="${freq}"
    # fi
done
