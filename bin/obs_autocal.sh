#! /bin/bash

usage()
{
echo "obs_autocal.sh [-d dep] [-a account] [-t] obsnum
  -p project : project, no default
  -d dep     : job number for dependency (afterok)
  -i         : disable the ionospheric metric tests (default = False)
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  -a         : Flag to use aocalibrate instead of hyperdrive? 
  -n         : Node type for dug (default=GXNODETYPE)
  -f FRAC    : the acceptable fraction of spectrum that may be flagged in a calibration
               solution file before it is marked as bad. Value between 0 - 1. (default = 0.25)
  -s SFRAC   : the acceptable fraction of a segmented spectrum that may be flagged in a 
               calibration solution file before it is flagged as bad. Typical GLEAM-X
               processing has four sub-bands, so there are four segments. If a single 
               segment has more then SFRAC flagged it is marked as bad. (default = 0.4) 
  obsnum     : the obsid to process, or a text file of obsids (newline separated). 
               A job-array task will be submitted to process the collection of obsids. " 1>&2;
exit 1;
}

pipeuser=${GXUSER}

dep=
tst=
ion=1
frac=0.25
sthresh=0.4
ao_calibrate=
nodetype=
# parse args and set options
while getopts ':tia:n:d:p:f:s:' OPTION
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
	i)
	    ion=
	    ;;
	t)
	    tst=1
	    ;;
    a)
        ao_calibrate=1
        ;;
    f)
        frac=${OPTARG}
        ;;
    s) 
        sthresh=${OPTARG}
        ;;
	? | : | h)
	    usage
	    ;;
  esac
done
# set the obsid to be the first non option
shift  "$(($OPTIND -1))"
obsnum=$1

# if obsid or project are empty then just print help
if [[ -z ${obsnum} || -z ${project} ]]
then
    usage
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

datadir="${GXSCRATCH}/$project"

# set dependency
if [[ ! -z ${dep} ]]
then
    if [[ -f ${obsnum} ]]
    then
        depend="--dependency=aftercorr:${dep}"
    else
        depend="--dependency=afterok:${dep}"
    fi
fi

script="${GXSCRIPT}/autocal_${obsnum}.sh"

cat "${GXBASE}/templates/autocal.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                     -e "s:DATADIR:${datadir}:g" \
                                     -e "s:IONOTEST:${ion}:g" \
                                     -e "s:PIPEUSER:${pipeuser}:g" \
                                     -e "s:OFFRINGA:${ao_calibrate}:g" \
                                     -e "s:FRACTION:${frac}:g" \
                                     -e "s:STHRESH:${sthresh}:g" > "${script}"


output="${GXLOG}/autocal_${obsnum}.o%A"
error="${GXLOG}/autocal_${obsnum}.e%A"

if [[ -f ${obsnum} ]]
then
   output="${output}_%a"
   error="${error}_%a"
fi

if [[ ${GXCOMPUTER} == "garrawarla" ]]
then
    CPUSPERTASK=3
    MEMPERTASK=15
elif [[ ${GXCOMPUTER} == "setonix" ]]
then 
    CPUSPERTASK=8
    MEMPERTASK=15
elif [[ ${GXCOMPUTER} == "dug" ]]
then
    CPUSPERTASK=5
    MEMPERTASK=32
else 
    CPUSPERTASK=${GXNCPUS}
    MEMPERTASK=${GXABSMEMORY}
fi


chmod 777 "${script}"

# sbatch submissions need to start with a shebang
# echo '#!/bin/bash' > ${script}.sbatch
# echo "srun --cpus-per-task=${CPUSPERTASK} --ntasks=1 --ntasks-per-node=1  singularity run ${GXCONTAINER} ${script}" >> ${script}

sub="sbatch --begin=now+1minutes --export=ALL --cpus-per-task=${CPUSPERTASK}  --mem=${MEMPERTASK}G --output=${output} --error=${error}"
sub="${sub} ${jobarray} ${depend} ${partition} ${script}"
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
        ${GXCONTAINER} track_task.py queue --jobid="${jobid}" --taskid="${taskid}" --task='calibrate' --submission_time="$(date +%s)" --batch_file="${script}" \
                            --obs_id="${obs}" --stderr="${obserror}" --stdout="${obsoutput}"
    fi

    echo "$obsoutput"
    echo "$obserror"
done
