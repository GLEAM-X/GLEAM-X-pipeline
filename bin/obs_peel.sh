#! /bin/bash

# Script to drive the peeling process. Originally based on the obs_calibrate.sh script. 
usage()
{
echo "obs_peel.sh [-d dep] [-p project] [-n nodetype] [-z] [-t] obsnum

    Script to drive the peeling process across a set of observation IDs.

  -d dep     : job number for dependency (afterok)
  -p prject  : project, must be specified (no default)
  -n nodetype: for DUG processing in case you want to send to fancy node 
  -z         : debugging option: work on the CORRECTED_DATA column instead of the DATA
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  obsnum     : the obsid to process" 1>&2;
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

# parse args and set options
while getopts ':td:q:' OPTION
do
    case "$OPTION" in
	d)
	    dep=${OPTARG}
	    ;;

	q)
	    queue="-p ${OPTARG}"
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

script="${GXSCRIPT}/peel_${obsnum}.sh"

cat ${GXBASE}/templates/peel.tmpl | sed -e "s:OBSNUM:${obsnum}:g" \
                                -e "s:BASEDIR:${base}:g" \
                                -e "s:DEBUG:${debug}:g" \
                                -e "s:NODETYPE:${nodetype}:g" \
                                -e "s:PIPEUSER:${pipeuser}:g" > ${script}

output="${GXLOG}/peel_${obsnum}.o%A"
error="${GXLOG}/peel_${obsnum}.e%A"

if [[ -f ${obsnum} ]]
then
   output="${output}_%a"
   error="${error}_%a"
fi


# TODO: Maybe check that it is appropriate for this! 
if [[ ${GXCOMPUTER} == "dug" ]]
then
    CPUSPERTASK=10
    MEMPERTASK=80
else 
    CPUSPERTASK=${GXNCPUS}
    MEMPERTASK=${GXABSMEMORY}
fi

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

    echo "$obsoutput"
    echo "$obserror"
done
