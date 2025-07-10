VMPATH="/data/Archived_Obsids/"
SAVEPATH="/data/curtin_gleam/GX_D-26_20180525"
FILENAME="/data/curtin_gleam/GX_D-26_20180525/GX_D-26_20180525.txt"

DRYRUN=''

echo """

Some of these commands will take a long time to start. The directories stored on the virtual machine are mounted across a network (a network link that spans Australia!). There might be periods where this process takes a long time to complete. Rest assured the rsync should be doing the right thing.  Just make sure you've set the filename correctly and it should work :) 

"""
set -x


## touch includefile.txt 
readarray -t arr < ${FILENAME}

for element in ${arr[@]}
    do
        rsync -avh $DRYRUN --progress "gleam-x-db:${VMPATH}/${element}/*-image-pb.fits" "${SAVEPATH}/${element}/"
        rsync -avh $DRYRUN --progress "gleam-x-db:${VMPATH}/${element}/${element}_deep-MFS-image-pb_bkg.fits" "${SAVEPATH}/${element}/${element}_deep-MFS-image-pb_bkg.fits"
        # rsync -avh $DRYRUN --progress "${VMUSER}@${VMADDR}:${VMPATH}/${element}/*-image-pb_warp_rescaled_weight.fits" "${SAVEPATH}/${element}/"
        rsync -avh $DRYRUN --progress "gleam-x-db:${VMPATH}/${element}/${element}_deep-MFS-image-pb_rms.fits" "${SAVEPATH}/${element}/${element}_deep-MFS-image-pb_rms.fits"
        rsync -avh $DRYRUN --progress "gleam-x-db:${VMPATH}/${element}/${element}_deep-MFS-image-pb_warp_comp.fits" "${SAVEPATH}/${element}/${element}_deep-MFS-image-pb_warp_comp.fits"
        wget -O ${element}.metafits http://ws.mwatelescope.org/metadata/fits?obs_id=${element}
            mv ${element}.metafits "${SAVEPATH}/${element}/${element}.metafits"
done

lastobsid=$(tail -n 1 ${FILENAME})

if [[ -e "${SAVEPATH}/${lastobsid}/${lastobsid}.metafits" ]]
then
        echo "Finished downloading everything!"
        exit 0
else
        echo "Something is wrong? Dont have the metafits for last obsid..." 
        exit 1
fi