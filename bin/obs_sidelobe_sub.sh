#! /bin/bash

usage()
{
echo "obs_sidelobe_sub.sh [-d dep] [-p project] [-a account] [-n nodetype] [-z] [-t] obsnum
  -d dep     : job number for dependency (afterok)
  -p project : project, (must be specified, no default)
  -z         : Debugging mode: image the CORRECTED_DATA column
                instead of imaging the DATA column
  -n node    : Node type for use in DUG
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  obsnum     : the obsid to process, or a text file of obsids (newline separated). 
               A job-array task will be submitted to process the collection of obsids. " 1>&2;
exit 1;
}

pipeuser="${GXUSER}"

#initial variables
dep=
tst=
debug=
# parse args and set options
while getopts ':tzd:a:n:p:' OPTION
do
    case "$OPTION" in
	d)
	    dep=${OPTARG}
	    ;;
    a)
        account=${OPTARG}
        ;;
    p)
        project=${OPTARG}
        ;;
    n) 
        nodetype=${OPTARG}
        ;;
    z)
        debug=1
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
obsnum=$1

queue="-p ${GXSTANDARDQ}"
base="${GXSCRATCH}/$project"
code="${GXBASE}"

# if obsid is empty then just print help

if [[ -z ${obsnum} ]] || [[ -z $project ]] || [[ ! -d ${base} ]]
then
    usage
fi

if [[ ! -z ${dep} ]]
then
    if [[ -f ${obsnum} ]]
    then
        depend="--dependency=aftercorr:${dep}"
    else
        depend="--dependency=afterok:${dep}"
    fi
fi

if [[ ! -z ${GXACCOUNT} ]]
then
    account="--account=${GXACCOUNT}"
fi

# Establish job array options
if [[ -f ${obsnum} ]]
then
    numfiles=$(wc -l "${obsnum}" | awk '{print $1}')
    jobarray="--array=1-${numfiles}"
else
    numfiles=1
    jobarray=''
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

# start the real program

script="${GXSCRIPT}/sidelobe_sub_${obsnum}.sh"
cat "${GXBASE}/templates/sidelobe_sub.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                 -e "s:BASEDIR:${base}:g" \
                                 -e "s:DEBUG:${debug}:g" \
                                 -e "s:NODETYPE:${nodetype}:g" \
                                 -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

output="${GXLOG}/sidelobe_sub_${obsnum}.o%A"
error="${GXLOG}/sidelobe_sub_${obsnum}.e%A"

if [[ -f ${obsnum} ]]
then
   output="${output}_%a"
   error="${error}_%a"
fi

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
# echo '#!/bin/bash' > ${script}.sbatch
# echo "srun --cpus-per-task=${GXNCPUS} --ntasks=1 --ntasks-per-node=1 singularity run ${GXCONTAINER} ${script}" >> ${script}.sbatch

GXNCPULINE="--ntasks-per-node=1 --cpus-per-task=15"


sub="sbatch --begin=now+5minutes --export=ALL  --time=06:00:00 --mem=50G --output=${output} --error=${error}"
sub="${sub} ${GXNCPULINE} ${account} ${jobarray} ${depend} ${script}"
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

echo "Submitted ${script} as ${jobid} . Follow progress here:"

for taskid in $(seq ${numfiles})
    do
    # rename the err/output files as we now know the jobid
    obserror=$(echo "${error}" | sed -e "s/%A/${jobid}/" -e "s/%a/${taskid}/")
    obsoutput=$(echo "${output}" | sed -e "s/%A/${jobid}/" -e "s/%a/${taskid}/")

    if [[ -f ${obsnum} ]]
    then
        obs=$(sed -n -e "${taskid}"p "${obsnum}")
    else
        obs=$obsnum
    fi

    if [ "${GXTRACK}" = "track" ]
    then
        # record submission
        ${GXCONTAINER} track_task.py queue --jobid="${jobid}" --taskid="${taskid}" --task='image' --submission_time="$(date +%s)" \
                            --batch_file="${script}" --obs_id="${obs}" --stderr="${obserror}" --stdout="${obsoutput}"
    fi

    echo "$obsoutput"
    echo "$obserror"
done

