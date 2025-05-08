#! /bin/bash

usage()
{
echo "drift_mosaic.sh [-p project] [-d dep] [-q queue] [-a account] [-t] [-f] [-r ra] [-e dec] [-m mosaicdir] [-s nscat] -o list_of_observations.txt
  -p project  : project, (must be specified, no default)
  -d dep      : job number for dependency (afterok)
  -t          : test. Don't submit job, just make the batch file
                and then return the submission command
  -f          : Use the data products produced by the filtered rescaling, which has 
                observations with high blur factors. This will only work if the 
                drift_rescale.sh task has been processed with a supplied -b psf option.  
  -r RA       : Right Ascension (decimal hours; default = guess from observation list)
  -s nscat    : Option for psf_select, do you want a different source catalogue for PSF creation/ddmod? Give name of catalogue and assumes in $GXBASE/models
  -e dec      : Declination (decimal degrees; default = guess from observation list)
  -m mosaicdir: Directory name for mosaics to be created (default=mosaic) 
  -o obslist  : the list of obsids to process" 1>&2;
exit 1;
}

pipeuser=$(whoami)

#initial variables
dep=
queue="-p ${GXSTANDARDQ}"
tst=
ra=
dec=
mosaicdir=
filtered=

# parse args and set options
while getopts ':td:p:o:r:e:m:s:f' OPTION
do
    case "$OPTION" in
    d)
        dep=${OPTARG} ;;
    p)
        project=${OPTARG} ;;
	o)
	    obslist=${OPTARG} ;;
    r)
        ra=${OPTARG} ;;
    e)
        dec=${OPTARG} ;;
    m) 
        mosaicdir=${OPTARG} ;;
    s)
        sourcecat=${OPTARG} ;;
    t)
        tst=1 ;;
    f) 
        filtered=1 ;;
    ? | : | h)
            usage ;;
  esac
done

# if obslist is not specified or an empty file then just print help

if [[ -z ${obslist} ]] || [[ ! -s ${obslist} ]] || [[ ! -e ${obslist} ]] || [[ -z $project ]]
then
    usage
else
    numfiles=$(wc -l ${obslist} | awk '{print $1}')
fi

if [[ ! -z ${dep} ]]
then
    depend="--dependency=afterok:${dep}"
fi

if [[ ! -z ${GXACCOUNT} ]]
then
    account="--partition=${GXACCOUNT}"
fi

queue="-p ${GXSTANDARDQ}"
base="${GXSCRATCH}/${project}"

obss=($(sort $obslist))
listbase=$(basename "${obslist}")
listbase=${listbase%%.*}
script="${GXSCRIPT}/mosaic_${listbase}.sh"

cat "${GXBASE}/templates/mosaic.tmpl" | sed -e "s:OBSLIST:${obslist}:g" \
                                      -e "s:RAPOINT:${ra}:g" \
                                      -e "s:DECPOINT:${dec}:g" \
                                      -e "s:BASEDIR:${base}:g" \
                                      -e "s:MOSAICDIR:${mosaicdir}:g" \
                                      -e "s:SOURCECAT:${sourcecat}:g" \
                                      -e "s:FILTERED:${filtered}:g" \
                                      -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

output="${GXLOG}/mosaic_${listbase}.o%A_%a"
error="${GXLOG}/mosaic_${listbase}.e%A_%a"

chmod 755 "${script}"

# # sbatch submissions need to start with a shebang
# echo '#!/bin/bash' > "${script}.sbatch"
# echo "srun --cpus-per-task=${GXNCPUS} --ntasks=1 --ntasks-per-node=1 singularity run ${GXCONTAINER} ${script}" >> "${script}.sbatch"

# Automatically runs a job array for each sub-band
sub="sbatch  --begin=now+5minutes --array=0-4  --export=ALL  --time=12:00:00 --mem=${GXABSMEMORY}G --output=${output} --error=${error}"
sub="${sub} ${GXNCPULINE} ${account} ${GXTASKLINE} ${depend} ${script}"
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
        ${GXCONTAINER} track_task.py queue_mosaic --jobid="${jobid}" --taskid="${taskid}" --task='mosaic' --submission_time="$(date +%s)" --batch_file="${script}" \
                                --batch_obs_id "${obss[@]}" --stderr="${terror}" --stdout="${toutput}" \
                                --subband="${subchan}"
    fi
done
