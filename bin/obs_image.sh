#! /bin/bash

usage()
{
echo "obs_image.sh [-d dep] [-p project] [-n nodetype] [-z] [-t] obsnum
  -d dep     : job number for dependency (afterok)
  -p project : project, (must be specified, no default)
  -z         : Debugging mode: image the CORRECTED_DATA column
                instead of imaging the DATA column
  -n node    : Node type for dug (default=GXNODETYPE)
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
nodetype=
# parse args and set options
while getopts ':tzd:p:n:' OPTION
do
    case "$OPTION" in
	d)
	    dep=${OPTARG}
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
    account="--partition=${GXACCOUNT}"
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

script="${GXSCRIPT}/image_${obsnum}.sh"
cat "${GXBASE}/templates/image.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                 -e "s:BASEDIR:${base}:g" \
                                 -e "s:DEBUG:${debug}:g" \
                                 -e "s:NODETYPE:${nodetype}:g" \
                                 -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

output="${GXLOG}/image_${obsnum}.o%A"
error="${GXLOG}/image_${obsnum}.e%A"

if [[ -f ${obsnum} ]]
then
   output="${output}_%a"
   error="${error}_%a"
fi


if [[ ${GXCOMPUTER} == "dug" ]]
then
    CPUSPERTASK=10
    MEMPERTASK=80
else 
    CPUSPERTASK=${GXNCPUS}
    MEMPERTASK=${GXABSMEMORY}
fi


chmod 777 "${script}"

# sbatch submissions need to start with a shebang
# echo '#!/bin/bash' > ${script}.sbatch
# echo "srun --cpus-per-task=${GXNCPUS} --ntasks=1 --ntasks-per-node=1 singularity run ${GXCONTAINER} ${script}" >> ${script}.sbatch

sub="sbatch --begin=now+1minutes --export=ALL  --time=03:00:00 --mem=${MEMPERTASK}G --cpus-per-task=${CPUSPERTASK} --output=${output} --error=${error}"
sub="${sub} ${partition} ${jobarray} ${depend} ${script}"
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

