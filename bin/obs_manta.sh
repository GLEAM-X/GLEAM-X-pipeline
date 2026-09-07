#! /bin/bash

usage() {
echo "obs_manta.sh [-p project] [-d dep] [-s timeave] [-k freqav] [-t] obsnum
  -d dep      : job number for dependency (afterok)
  -p project  : project, (must be specified, no default)
  -s timeres  : time resolution in sec. default = 2 s
  -k freqres  : freq resolution in KHz. default = 40 kHz
  -f edgeflag : number of edge band channels flagged. default = 80
  -g          : download gpubox fits files instead of measurement sets
  -t          : test. Don't submit job, just make the batch file
                and then return the submission command
  obsnum      : the obsid to process, or a text file of obsids (newline separated)." 1>&2;
exit 1;
}

# Supercomputer options
# Hardcode for downloading
if [[ -n $GXCOPYA ]]; then
    account="--account ${GXCOPYA}"
fi
standardq="${GXCOPYQ}"

pipeuser=$(whoami)

# initial variables
dep=
queue="-p $standardq"
tst=
gpubox=
timeres=
freqres=
edgeflag=80

# parse args and set options
while getopts ':tgd:p:s:k:f:e:' OPTION; do
    case "$OPTION" in
    d)
        dep=${OPTARG} ;;
    p)
        project=${OPTARG} ;;
	s)
	    timeres=${OPTARG} ;;
	k)
	    freqres=${OPTARG} ;;
    t)
        tst=1 ;;
    g)
        gpubox=1 ;;
    f)
        edgeflag=${OPTARG} ;;
    ? | : | h)
        usage ;;
    esac
done
shift  "$(($OPTIND -1))"
obsnum=$@

# If obsnum is not specified or is an empty file or project directory is not specified then just print help.
if [[ -z ${obsnum} ]] || ([[ -f ${obsnum} ]] && [[ ! -s ${obsnum} ]]) || [[ -z $project ]]; then
    usage
fi

if [[ -n ${dep} ]]; then
    depend="--dependency=afterok:${dep}"
fi

# Add the metadata to the observations table in the database
# import_observations_from_db.py --obsid "${obsnum}"

base="${GXSCRATCH}/${project}"
cd "${base}" || exit 1

dllist=""
if [[ ! -f "${obsnum}" ]]; then
    list=${obsnum}
else
    list=$(cat "${obsnum}")
fi

echo "" > "${obsnum}_manta.tmp"

# Set up telescope-configuration-dependent options
# Might use these later to get different metafits files etc
for obsid in $list; do
    # Note this implicitly 
    if [[ $obsid -lt 1151402936 ]]; then
        telescope="MWA128T"
        basescale=1.1
        if [[ -z $freqres ]]; then freqres=40; fi
        if [[ -z $timeres ]]; then timeres=4; fi
    elif [[ $obsid -ge 1151402936 ]] && [[ $obsid -lt 1191580576 ]]; then
        telescope="MWAHEX"
        basescale=2.0
        if [[ -z $freqres ]]; then freqres=40; fi
        if [[ -z $timeres ]]; then timeres=8; fi
    elif [[ $obsid -ge 1191580576 ]]; then
        telescope="MWALB"
        basescale=0.5
        if [[ -z $freqres ]]; then freqres=40; fi
        if [[ -z $timeres ]]; then timeres=4; fi
    fi

    if [[ -d "${obsid}/${obsid}.ms" ]]; then
        echo "${obsid}/${obsid}.ms already exists. I will not download it again."
    else
        if [[ -z ${gpubox} ]]; then
            echo "obs_id=${obsid}, preprocessor=birli, delivery=scratch, job_type=c, avg_time_res=${timeres}, avg_freq_res=${freqres}, flag_edge_width=${edgeflag}, output=ms" >>  "${obsnum}_manta.tmp"
            stem="ms"
        else
            echo "obs_id=${obsid}, delivery=acacia, job_type=d, download_type=vis" >>  "${obsnum}_manta.tmp"
            stem="vis"
        fi
        dllist=$dllist"$obsid "
    fi
done

listbase=$(basename ${obsnum})
listbase=${listbase%%.*}
script="${GXSCRIPT}/manta_${listbase}.sh"

cat "${GXBASE}/templates/manta.tmpl" | sed -e "s:OBSLIST:${obsnum}:g" \
                                 -e "s:STEM:${stem}:g"  \
                                 -e "s:TRES:${timeres}:g" \
                                 -e "s:FRES:${freqres}:g" \
                                 -e "s:BASEDIR:${base}:g" \
                                 -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

output="${GXLOG}/manta_${listbase}.o%A"
error="${GXLOG}/manta_${listbase}.e%A"

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > "${script}.sbatch"
echo "srun --export=all singularity run ${GXCONTAINER} ${script}" >> "${script}.sbatch"

# This is the only task that should reasonably be expected to run on another cluster. 
# Export all GLEAM-X pipeline configurable variables and the MWA_ASVO_API_KEY to ensure 
# obs_manta completes as expected
sub="sbatch --begin=now+1minutes --mem=10G --export=$(echo ${!GX*} | tr ' ' ','),MWA_ASVO_API_KEY,SINGULARITY_BINDPATH  --time=08:00:00 -M ${GXCOPYM} --output=${output} --error=${error}"
sub="${sub} ${depend} ${account} ${queue} ${script}.sbatch"

if [[ -n ${tst} ]]; then
    echo "script is ${script}"
    echo "submit via:"
    echo "${sub}"
    exit 0
fi

# submit job
jobid=($(${sub}))
jobid=${jobid[3]}

# rename the err/output files as we now know the jobid
error="${error//%A/${jobid[0]}}"
output="${output//%A/${jobid[0]}}"

# record submission
n=1
if [[ "${GXTRACK}" == "track" ]]; then
    for obsid in $dllist; do
        ${GXCONTAINER} track_task.py queue \
                        --jobid="${jobid[0]}" \
                        --taskid="${n}" \
                        --task='download' \
                        --submission_time="$(date +%s)" \
                        --batch_file="${script}" \
                        --obs_id="${obsid}" \
                        --stderr="${error}" \
                        --stdout="${output}"
    done
    ((n+=1))
fi

echo "Submitted ${script} as ${jobid}. Follow progress here:"
echo "${output}"
echo "${error}"
