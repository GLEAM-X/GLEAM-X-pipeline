#! /bin/bash

usage()
{
echo "drift_plus20_weightmap.sh [-p project] [-d dep] [-q queue] [-a account] [-t] [-m ra_min] [-x ra_max ] nightname

Task to prepare the data for a night's worth of drift scan observations for final mosaicking. 
This include running BANE/Aegean to make sure there is the noise and background images, and also calculate
the weighting image using a sigmoid function. Takes a lengthy time hopefully only need to run once. 
TO DO: potentially improve so can run in parallel for each night. 

  -p project  : project, (must be specified, no default)
  -d dep     : job number for dependency (afterok)
  -t          : test. Don't submit job, just make the batch file
                and then return the submission command
  -n node     : Node type for dug (default=GXNODETYPE)
  nightlist  : the list of nights with existing coadded images to process" 1>&2;
exit 1;
}

pipeuser=$(whoami)

#initial variables
dep=
tst=
nodetype=
ra_min=
ra_max=
# parse args and set options
while getopts ':td:p:n:x:m:' OPTION
do
    case "$OPTION" in
    d)
        dep=${OPTARG} ;;
    p)
        project=${OPTARG} ;;
    x)
        ra_max=${OPTARG} ;;
    m)
        ra_min=${OPTARG} ;;
    n)
        nodetype=${OPTARG} ;;
    t)
        tst=1 ;;
    ? | : | h)
            usage ;;
  esac
done
# set the nightlist to be the first non option
shift  "$(($OPTIND -1))"
nightname=$1

# if obslist is not specified or an empty file then just print help

if [[ -z ${nightname} ]] || [[ ! -s ${nightname} ]] || [[ ! -e ${nightname} ]] || [[ -z $project ]]
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

listbase=$(basename "${nightname}")
listbase=${listbase%%.*}
script="${GXSCRIPT}/plus20_weightmap_${listbase}.sh"

cat "${GXBASE}/templates/plus20_weightmaps.tmpl" | sed -e "s:NIGHTNAME:${nightname}:g" \
                                      -e "s:BASEDIR:${base}:g" \
                                      -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

output="${GXLOG}/plus20_weightmap_${listbase}.o%A_%a"
error="${GXLOG}/plus20_weightmap_${listbase}.e%A_%a"

chmod 755 "${script}"

# Automatically runs a job array for each sub-band
sub="sbatch  --begin=now --array=0-24  --export=ALL  --time=01:00:00 --mem=100G --output=${output} --error=${error}"
sub="${sub} ${GXNCPULINE} ${partition} ${depend} ${queue} ${script}"


if [[ ! -z ${tst} ]]
then
    echo "script is ${script}"
    echo "submit via:"
    echo "${sub}"
    exit 0
fi

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
