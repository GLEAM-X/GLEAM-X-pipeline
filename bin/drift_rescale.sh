#! /bin/bash

usage()
{
echo "drift_rescale.sh [-p project] [-d dep] [-b projectpsf] [-a account] [-t] [-r] [-e dec] -o list_of_observations.txt
  -p project  : project, (must be specified, no default)
  -d dep     : job number for dependency (afterok)
  -t          : test. Don't submit job, just make the batch file
                and then return the submission command
  -r read : read existing solutions instead of writing new ones
  -b projpsf : the path to the projpsf_psf.fits data producted produced by drift_mosaic.sh. Used to identify obsids with high blur factors
  -o obslist  : the list of obsids to process" 1>&2;
exit 1;
}

pipeuser=$(whoami)

dep=
tst=
readfile=
projpsf=

# parse args and set options
while getopts ':td:p:o:rb:' OPTION
do
    case "$OPTION" in
    d)
        dep=${OPTARG} ;;
    p)
        project=${OPTARG} ;;
	o)
	    obslist=${OPTARG} ;;
    r)
        readfile="--read" ;;
    t)
        tst=1 ;;
    b)
        projpsf="${OPTARG}" ;;
    ? | : | h)
        usage ;;
  esac
done

# if obslist is not specified or an empty file then just print help

if [[ -z ${obslist} ]] || [[ ! -s ${obslist} ]] || [[ ! -e ${obslist} ]] || [[ -z $project ]]
then
    usage
else
    numfiles=$(wc -l "${obslist}" | awk '{print $1}')
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
cd "${base}" || exit

obss=($(sort $obslist))
listbase=$(basename "${obslist}")
listbase=${listbase%%.*}
script="${GXSCRIPT}/rescale_${listbase}.sh"

cat "${GXBASE}/templates/rescale.tmpl" | sed -e "s:OBSLIST:${obslist}:g" \
                                             -e "s:READ:${readfile}:g" \
                                             -e "s:BASEDIR:${base}:g"  \
                                             -e "s:PROJECTPSF:${projpsf}:g" \
                                             -e "s:PIPEUSER:${pipeuser}:g" > ${script}

output="${GXLOG}/rescale_${listbase}.o%A_%a"
error="${GXLOG}/rescale_${listbase}.e%A_%a"

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > "${script}.sbatch"
echo "singularity run ${GXCONTAINER} ${script}" >> "${script}.sbatch"

# Automatically runs a job array for each sub-band
sub="sbatch  --begin=now+5minutes --array=0-4 --export=ALL  --time=12:00:00 --mem=${GXABSMEMORY}G -M ${GXCOMPUTER} --output=${output} --error=${error}"
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
error="${error//%A/${jobid}}"
output="${output//%A/${jobid}}"

subchans=(0000 0001 0002 0003 MFS)
echo "Submitted ${script} as ${jobid} . Follow progress here:"

# record submission
for taskid in $(seq 0 1 4)
do
    terror="${error//%a/${taskid}}"
    toutput="${output//%a/${taskid}}"
    subchan=${subchans[$taskid]}

    echo "${toutput}"
    echo "${terror}"

    if [ "${GXTRACK}" = "track" ]
    then
    obsnum=$(cat "${obslist}")
    ${GXCONTAINER} track_task.py queue_mosaic --jobid="${jobid}" --taskid="${taskid}" --task='rescale' --submission_time="$(date +%s)" --batch_file="${script}" \
                        --batch_obs_id ${obsnum} --stderr="${terror}" --stdout="${toutput}" --subband="${subchan}"
    fi
done
