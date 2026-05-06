#! /bin/bash

usage()
{
echo "drift_confusion_noise.sh [-p project] [-d dep] [-t] [-m mosaicdir] -n mosaic_name
  -p project  : project, (must be specified, no default)
  -d dep      : job number for dependency (afterok)
  -t          : test. Don't submit job, just make the batch file
                and then return the submission command  
  -m mosaicdir: Directory name where mosaics stored (default=project/mosaic) 
  -n mosaicnm : Name of the mosaic, typically the drift name e.g. XG_D-27_20201015 (no default, must be specified)" 1>&2;
exit 1;
}

pipeuser=$(whoami)

# initial variables 
dep=
queue="-p ${GXSTANDARDQ}"
tst=
mosaicdir=

# parse args and set options
while getopts ':td:p:b:m:l:r:c:n:' OPTION
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
    n)
        mosaicnm=${OPTARG} ;;
    ? | : | h)
            usage ;;
  esac
done

if [[ -z ${project} ]] || [[ -z ${mosaicnm} ]]
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

base="${GXSCRATCH}/${project}"
listbase=$(basename "${mosaicnm}")
listbase=${listbase%%.*}

script="${GXSCRIPT}/confusion_noise_${listbase}.sh"

cat "${GXBASE}/templates/confusion_noise.tmpl" | sed -e "s:BASEDIR:${base}:g" \
                                                -e "s:PIPEUSER:${pipeuser}:g" \
                                                -e "s:MOSAICNM:${mosaicnm}:g" \
                                                -e "s:MOSAICDIR:${mosaicdir}:g" > ${script}

output="${GXLOG}/confusion_noise_${listbase}.o%A_%a"
error="${GXLOG}/confusion_noise_${listbase}.e%A_%a"

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
# echo '#!/bin/bash' > "${script}.sbatch"
# echo "srun --cpus-per-task=${GXNCPUS} --ntasks=1 --ntasks-per-node=1 singularity run ${GXCONTAINER} ${script}" >> "${script}.sbatch"

# Automatically runs a job array for each sub-band
sub="sbatch  --begin=now+5minutes --array=0-4  --export=ALL  --time=20:00:00 --mem=80G --output=${output} --error=${error}"
sub="${sub} --ntasks-per-node=1 --cpus-per-task=60 ${depend} ${queue} ${script}"
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
for taskid in $(seq 1 1 24)
do
    terror="${error//%a/${taskid}}"
    toutput="${output//%a/${taskid}}"
    subchan=${subchans[$taskid]}

    echo "${toutput}"
    echo "${terror}"

done 
