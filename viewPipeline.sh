#!/bin/bash

fslview exampleData/sub-M10999905_ses-ALGA_task-rest_acq-1400_bold.nii.gz

fslview fmriPipeline/process_timeseries/mcflirt/sub-M10999905_ses-ALGA_T1w_mcf.nii

fslview fmriPipeline/process_timeseries/meanimage/sub-M10999905_ses-ALGA_T1w_mcf_mean.nii

echo \(bet\) skullstripped fmri mean image mask
fslview fmriPipeline/process_timeseries/bet/sub-M10999905_ses-ALGA_T1w_mcf_mean_brain_mask.nii

echo \(bet\) skullstripped fmri mean image result
fslview fmriPipeline/process_timeseries/bet/sub-M10999905_ses-ALGA_T1w_mcf_mean_brain.nii

echo rcfe from mean fmri image and the skulltripping mask
fslview fmriPipeline/process_timeseries/zcale/rcfe.nii

echo skullstripped structural image
fslview fmriPipeline/process_timeseries/skullstrip/sub-M10999905_ses-ALGA_task-rest_acq-1400_bold_skullstrip.nii

echo \(flirt\) the product of coregistering the skulltripped mean fmri image to the skullstripped structural image
fslview fmriPipeline/process_timeseries/flirt/sub-M10999905_ses-ALGA_T1w_mcf_mean_brain_flirt.nii.gz

echo coregistering the rcfe image to the structural space, using the matrix produced registering the mean fmri to the skullstripped t1

fslview fmriPipeline/process_timeseries/coreg/rcfe_flirt.nii.gz

echo warping the T1 image to the MNI152 template

fslview fmriPipeline/process_timeseries/warp152/ants_deformed.nii.gz  

echo registering the structrual space registed rcfe image to the template space using the warp field and affine transform produced by registering the Structural image to the MNI152 template

fslview fmriPipeline/process_timeseries/coreg2/rcfe_flirt_trans.nii.gz

echo performing an isotropic smooth on the template registered rcfe image

fslview fmriPipeline/process_timeseries/isoSmooth/rcfe_flirt_trans_smooth.nii 


