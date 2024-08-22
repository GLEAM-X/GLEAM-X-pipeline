#! /bin/bash

usage()
{
echo "drift_prepmosaic.sh [-p project] [-d dep] [-t] [-m mosaicdir] -o obslist
  -p project  : project, (must be specified, no default)
  -d dep      : job number for dependency (note: haven't actually implemented since array dependence is weird and this won't actually submit an array job so haven't figured out what to do with this yet.)
  -t          : test. Don't submit job, just make the batch file
                and then return the submission command  
  -m mosaicdir: Directory name where mosaics stored (default=project/mosaic) 
  -o obslist  : .txt file with the list of obsids in the mosaic (note it will use this to find the cenchan ones and name the mosaic" 1>&2;
exit 1;
}

pipeuser=$(whoami)

# initial variables 
dep=
tst=
mosaicdir=

# parse args and set options
while getopts ':td:p:m:o:' OPTION
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
    o)
        obslist=${OPTARG} ;;
    ? | : | h)
            usage ;;
  esac
done

if [[ -z ${project} ]] || [[ -z ${obslist} ]]
then
    usage
fi

queue="-p ${GXSTANDARDQ}"
base="${GXSCRATCH}/$project"

listbase=$(basename "${obslist}")
listbase=${listbase%%.*}
script="${GXSCRIPT}/prepmosaic_${listbase}.sh"


cat "${GXBASE}/templates/prepmosaic.tmpl" | sed -e "s:BASEDIR:${base}:g" \
                                                -e "s:PIPEUSER:${pipeuser}:g" \
                                                -e "s:OBSLIST:${obslist}:g" > ${script}


output="${GXLOG}/prepmosaic_${listbase}.o%A"
error="${GXLOG}/prepmosaic_${listbase}.e%A"

chmod 755 "${script}"

# # sbatch submissions need to start with a shebang
# echo '#!/bin/bash' > "${script}.sbatch"
# echo "srun --cpus-per-task=1 --ntasks=1 --ntasks-per-node=1 singularity run ${GXCONTAINER} ${script}" >> "${script}.sbatch"

# Automatically runs a job array for each sub-band
sub="sbatch  --begin=now+5minutes --export=ALL  --time=01:00:00 --mem=${GXABSMEMORY}G --output=${output} --error=${error}"
sub="${sub} ${GXNCPULINE} --partition=${GXSTANDARDQ} ${GXTASKLINE} ${depend} ${queue} ${script}"
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

echo "${output}"
echo "${error}"
