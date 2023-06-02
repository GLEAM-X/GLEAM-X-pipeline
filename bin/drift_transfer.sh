#! /bin/bash

endpoint='146.118.68.233' #HOST is already used as a keyword in other script
user='ubuntu'
remote='/mnt/gxarchive/Archived_Obsids'
port=

usage()
{
echo "drift_archive.sh [-d dep] [-p project] [-a account] [-u user] [-e endpoint] [-r remote_directory] [-q port] [-t] obsnum

Will rsync files over to a remote end point. It is expected that items have already been packaged for transfer by running drift_archive_prep.sh

Only a single process will be invoked for all obsids. There is no attempt to multi-process. 

  -d dep      : job number for dependency (afterok)
  -p project  : project, (must be specified, no default)
  -u user     : user name of system to archive to (default: '$user')
  -e endpoint : hostname to copy the archive data to (default: '$endpoint')
  -r remote   : remote directory to copy files to (default: '$remote')
  -t          : test. Don't submit job, just make the batch file
                and then return the submission command
  -o obsnum   : A text file of obsids (newline separated).  
  -q port     : The port number for rsync to use. (default: 22)" 1>&2;
exit 1;
}

if [[ -z ${GXSSH} ]] || [[ ! -r "${GXSSH}" ]]
then
    echo "The GXSSH variable has not been configured, or the corresponding key can not be accessed. "
    echo 'Ensure the ssh key exists and is correctly described in the GLEAM-X profile script.'
    echo 'If necessary a key pair can be created with ssh-keygen -t rsa -f "${GXBASE}/ssh_keys/gx_${GXUSER}"'
    echo "drift_transfer.sh will not attempt to archive. "
    exit 1
fi

pipeuser="${GXUSER}"

#initial variables
dep=
tst=

# parse args and set options
while getopts ':td:a:p:u:e:r:o:q:' OPTION
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
	u)
        user=${OPTARG}
        ;;
    e)
        endpoint=${OPTARG}
        ;;
    r)
        remote=${OPTARG}
        ;;  
    t)
	    tst=1
	    ;;
    o)
	    obslist=${OPTARG} 
        ;;
	q) 
        port=${OPTARG}
        ;;
    ? | : | h)
	    usage
	    ;;
  esac
done

queue="-p ${GXCOPYQ}"
base="${GXSCRATCH}/${project}"

# if obsid is empty then just print help

if [[ -z ${obslist} ]] || [[ -z $project ]] || [[ ! -d ${base} ]]
then
    usage
fi

if [[ ! -z ${dep} ]]
then
    depend="--dependency=afterok:${dep}"
fi

if [[ ! -z ${GXCOPYA} ]]
then
    account="--account=${GXCOPYA}"
fi

if [[ -n ${port} ]]
then 
    # Passed to rsync
    port="-p ${port}"
fi

numfiles=$(wc -l "${obslist}" | awk '{print $1}')

# start the real program
script="${GXSCRIPT}/transfer_${obslist}.sh"
cat "${GXBASE}/templates/transfer.tmpl" | sed -e "s:OBSLIST:${obslist}:g" \
                                 -e "s:BASEDIR:${base}:g" \
                                 -e "s:ENDUSER:${user}:g" \
                                 -e "s:ENDPOINT:${endpoint}:g" \
                                 -e "s:REMOTE:${remote}:g" \
                                 -e "s:PIPEUSER:${pipeuser}:g" \
                                 -e "s:PROJECT:${project}:g" \
                                 -e "s:PORT:${port}:g" > "${script}"

output="${GXLOG}/transfer_${obslist}.o%A"
error="${GXLOG}/transfer_${obslist}.e%A"

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > "${script}.sbatch"
# echo 'module load singularity/3.8.6' >> "${script}.sbatch"
# echo "export SINGULARITY_BINDPATH=${SINGULARITY_BINDPATH}" >> "${script}.sbatch"
echo "srun --export=all --cpus-per-task=1 --ntasks=1 --ntasks-per-node=1 singularity run ${GXCONTAINER} ${script}" >> "${script}.sbatch"

if [ ! -z ${GXNCPULINE} ]
then
    # archive only needs a single CPU core
    GXNCPULINE="--ntasks-per-node=1"
fi

# This is among the few tasks that should reasonably be expected to run on another cluster. 
# Export all GLEAM-X pipeline configurable variables 
sub="sbatch  --begin=now+5minutes --export=$(echo ${!GX*} | tr ' ' ','),SINGULARITY_BINDPATH --time=48:00:00 --mem=24G -M ${GXCOPYM} --output=${output} --error=${error} "
sub="${sub}  ${GXNCPULINE} ${account} ${GXTASKLINE} ${depend} ${queue} ${script}.sbatch"

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

# rename the err/output files as we now know the jobid
obserror=$(echo "${error}" | sed -e "s/%A/${jobid}/" -e "s/%a/${taskid}/")
obsoutput=$(echo "${output}" | sed -e "s/%A/${jobid}/" -e "s/%a/${taskid}/")

echo "${obsoutput}"
echo "${obserror}"

for taskid in $(seq ${numfiles})
    do

    obs=$(sed -n -e "${taskid}p" "${obslist}")

    if [ "${GXTRACK}" = "track" ]
    then
        echo "Submitting track_task for ${taskid} / ${obs}"
        # record submission
        ${GXCONTAINER} track_task.py queue --jobid="${jobid}" --taskid="${taskid}" --task='transfer' --submission_time="$(date +%s)" --batch_file="${script}" \
                            --obs_id="${obs}" --stderr="${obserror}" --stdout="${obsoutput}"
    fi

done
