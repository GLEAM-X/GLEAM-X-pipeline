#! /bin/bash

usage()
{
echo "drift_deep_coadd.sh [-p project] [-d dep] [-q queue] [-a account] [-t] [-f] 
  -p project  : project, (must be specified, no default)
  -d dep      : job number for dependency (afterok)
  -t          : test. Don't submit job, just make the batch file
                and then return the submission command
  -m mosaicdir: Directory name for mosaics to be created (default = mosaic)" 1>&2;
exit 1;
}

pipeuser=$(whoami)

#initial variables
dep=
queue="-p ${GXSTANDARDQ}"
tst=
mosaicdir=mosaic

# parse args and set options
while getopts ':td:p:m:' OPTION
do
    case "$OPTION" in
    d)
        dep=${OPTARG} ;;
    p)
        project=${OPTARG} ;;
	m) 
        mosaicdir=${OPTARG} ;;
    t)
        tst=1 ;;
    ? | : | h)
            usage ;;
  esac
done

# if project not specified or an empty file then just print help

if [[ -z $project ]]
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
base="${GXSCRATCH}/${project}/${mosaicdir}"

if [[ ! -e "${base}" ]]
then 
    echo "Path ${base} does not exist. "
    echo "Confirm -p ${project} and -m ${mosaicdir} are correct"
fi


obss=($(sort $obslist))
listbase=$(basename "${obslist}")
listbase=${listbase%%.*}
script="${GXSCRIPT}/mosaic_${listbase}.sh"

cat "${GXBASE}/templates/deep_coadd.tmpl" | sed -e "s:BASEDIR:${base}:g" \
                                      -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

output="${GXLOG}/deep_coadd_${listbase}.o%A_%a"
error="${GXLOG}/deep_coadd_${listbase}.e%A_%a"

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > "${script}.sbatch"
echo "srun ${GXSRUNLINE} singularity run ${GXCONTAINER} ${script}" >> ${script}.sbatch
# Automatically runs a job array for each sub-band
sub="sbatch  --begin=now+5minutes --array=0-4  --export=ALL  --time=24:00:00 --mem=${GXABSMEMORY}G -M ${GXCOMPUTER} --output=${output} --error=${error}"
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

echo "Submitted ${script} as ${jobid} . Follow progress here:"

# record submission
if [ "${GXTRACK}" = "track" ]
then
    ${GXCONTAINER} track_task.py queue_mosaic --jobid="${jobid}" --taskid="0" --task='deep_coadd' --submission_time="$(date +%s)" --batch_file="${script}" \
                            --batch_obs_id "123456789023" --stderr="${error}" --stdout="${output}" \
                            --subband="MFS"
fi
