#! /bin/bash

usage()
{
echo "drift_join_cats.sh [-p project] [-d dep] [-t] [-m mosaicdir] [-c comb_freq] -n mosaic_name
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
comb_freq=

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
    c)
        comb_freq=${OPTARG} ;;
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

queue="-p ${GXSTANDARDQ}"
base="${GXSCRATCH}/${project}"

if [[ ! -z ${GXACCOUNT} ]]
then
    account="--account=${GXACCOUNT}"
fi

if [[ ! -z ${nodetype} ]]
then 
    if [[ ${GXCOMPUTER} == "dug" ]]
    then
        partition="--constraint=${nodetype} --partition=${GXSTANDARDQ}"
        export GXCONTAINER="${GXCONTAINERPATH}/gleamx_tools_${nodetype}.img"
        echo ${GXCONTAINER}
    else 
        partition="--partition=${GXSTANDARDQ}"
    fi 
else
    if [[ ${GXCOMPUTER} == "dug" ]]
    then
        partition="--constraint=${GXNODETYPE} --partition=${GXSTANDARDQ}"
    else 
        partition="--partition=${GXSTANDARDQ}"
    fi 
fi 

base="${GXSCRATCH}/${project}"
listbase=$(basename "${mosaicnm}")
listbase=${listbase%%.*}
script="${GXSCRIPT}/join_cats_${listbase}.sh"

cat "${GXBASE}/templates/join_cats.tmpl" | sed -e "s:BASEDIR:${base}:g" \
                                                -e "s:PIPEUSER:${pipeuser}:g" \
                                                -e "s:MOSAICNM:${mosaicnm}:g" \
                                                -e "s:MOSAICDIR:${mosaicdir}:g" \
                                                -e "s:COMB_FREQ:${comb_freq}:g" > ${script}

output="${GXLOG}/join_cats_${listbase}.o%A"
error="${GXLOG}/join_cats_${listbase}.e%A"

chmod 755 "${script}"

# # sbatch submissions need to start with a shebang
# echo '#!/bin/bash' > "${script}.sbatch"
# echo "srun --cpus-per-task=${GXNCPUS} --ntasks=1 --ntasks-per-node=1 singularity run ${GXCONTAINER} ${script}" >> "${script}.sbatch"

# Automatically runs a job array for each sub-band
sub="sbatch  --begin=now+5minutes --export=ALL  --time=00:30:00 --mem=${GXABSMEMORY}G --output=${output} --error=${error}"
sub="${sub} ${GXNCPULINE} ${partition} ${depend} ${queue} ${script}"
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


echo "Submitted ${script} as ${jobid} Follow progress here:"
# rename the err/output files as we now know the jobid
error=${error//%A/"${jobid}"}
output=${output//%A/"${jobid}"}

echo "$output"
echo "$error"

