import nipype
import os
from os.path import abspath
from nipype import Workflow, Node, MapNode, Function

from nipype.interfaces.fsl import MCFLIRT, maths, BET, FLIRT
from nipype.interfaces.fsl.maths import MeanImage, IsotropicSmooth
from nipype.interfaces.utility import Merge
from nipype.interfaces.afni import SkullStrip
from nipype.interfaces.ants import WarpImageMultiTransform, Registration, legacy, ApplyTransforms, N4BiasFieldCorrection
import argparse
import nibabel as nib

import numpy as np
import nipype.interfaces.io as nio
from nipype.interfaces.io import BIDSDataGrabber
from bids import BIDSLayout
from nipype import DataGrabber




"""
Inputs:
1) fMRI timeseries
2) T1 Structural Image
3) template image

processing:
1) motion correction (mcflrt);
    compute mean (fslmaths);
    skull strip (BET);
    scaling within mask: zscale (python code or fslstats + fslmaths),multiply by -1 = rcFe;                              
    coregister mean fMRI to skullstripped T1 (FLIRT)    60oF     -> image, mat file

2) skull strip (afni 3dSkullStrip);
    warp whole head (not skull stripped) T1 to MNI 152 T1 2mm template (ANTS).
                                                                                   -> mat file/txt, image and coff file
3) apply combined coregistration from fMRI to T1 to MNI Template to rcFe (ANTS);
    apply spatial smoothing (4mm iso gaussian; fslmaths).
"""

accept_input = Workflow(name='take_input')


def handle_input_files(time_series=None, struct=None):
    if type(time_series) is not list and type(struct) is not list:
        return time_series, struct
    # The BIDSDatagrabber resulted in a list containing a list, this jsut remove the wrapping list
    return time_series[0], struct[0]
input_handler_node = Node(Function(function=handle_input_files, output_names=['time_series', 'struct']), name='input_handler')

# Motion correction on fmri time series
mcflirt_node = Node(MCFLIRT(mean_vol=True, output_type='NIFTI'), name="mcflirt")

# Compute mean(fslmaths) of the fmri time series
mean_fmri_node = Node(MeanImage(output_type='NIFTI'), name="meanimage")

# Skull Strip the fmri time series
bet_fmri_node = Node(BET(output_type='NIFTI', mask=True), name="bet_fmri")

# Bias Correct the fmri time series
bias_correction_node = Node(N4BiasFieldCorrection(), name='bias_correction')


def compute_scFe(input_image, mask_image, invert_sign=True):
    import nibabel as nib
    import numpy as np
    from scipy import stats
    from os import path
    '''
    Just in case you want to return just the image (e.g. rendering or
    further processing).
    Author: Stan Colcombe
    '''
    in_image = nib.load(input_image).get_data()
    m_image = nib.load(mask_image).get_data()
    out_image = np.zeros(in_image.shape)
    idx = np.where(m_image)
    if (invert_sign):
        out_image[idx] = stats.zscore(in_image[idx]) * -1.0
    else:
        out_image[idx] = stats.zscore(in_image[idx])
        print("Note: NOT inverting z-scores.")
    # return(nib.Nifti1Image(out_image, nib.load(input_image).affine))
    img = nib.Nifti1Image(out_image, nib.load(input_image).affine)
    img.to_filename("rcfe.nii")

    # nib.save(img, "rcfe.nii.gz")
    return path.abspath("rcfe.nii")


# Returns the relative concentration of brain iron
rcfe_node = Node(Function(input_names=['input_image', 'mask_image'], output_names=['output_image'], function=compute_scFe),
                 name="rcfe")

# coregister (skullstripped) mean of the fmri time series to the skull stripped T1 structural
flirt_node = Node(FLIRT(dof=6), name="flirt", cost='mutualinfo')  # do i have to specify out_matrix_file???

# skullstrip the T1 structural image
skullstrip_structural_node = Node(SkullStrip(outputtype='NIFTI'), name='skullstrip')

# Warp whole head T1 Structural Image to MNI 152 template
warp_to_152_node = Node(legacy.GenWarpFields(similarity_metric="CC"), name="warp152")

# coreg_to_struct_space = Node(FLIRT(apply_xfm=True, reference=struct_image, interp="sinc"), name="coreg")
coreg_to_struct_space_node = Node(FLIRT(apply_xfm=True, interp="sinc", cost='mutualinfo'), name="coreg_to_struct_space")

# coreg_to_template_space_node = Node(ApplyTransforms(reference_image=template, interpolation='BSpline'), name="coreg_to_template_space")
coreg_to_template_space_node = Node(ApplyTransforms(interpolation='BSpline'), name="coreg_to_template_space")

merge_transforms_node = Node(Merge(2), iterfield=['in2'], name="merge")

# Spatial smoothing
iso_smooth_node = Node(IsotropicSmooth(fwhm=4, output_type="NIFTI"), name='isoSmooth')

data_sink_node = Node(nio.DataSink(base_directory="results_dir", container='warp152_output', infields=['tt']),
                      name='dataSink')



make_rcfe = Workflow(name='make_rcfe')
make_rcfe.connect(mcflirt_node, 'out_file', mean_fmri_node, 'in_file')
make_rcfe.connect(mean_fmri_node, 'out_file', bet_fmri_node, 'in_file')
# make_rcfe.connect(mean_fmri_node, 'out_file', rcfe_node, 'input_image') #TODO: uncomment this, and disconect N4bias from rcfe node later
make_rcfe.connect(bet_fmri_node, 'mask_file', rcfe_node, 'mask_image')
# make_rcfe.connect(bet_fmri_node)

# if args['bias_correction'] is 'True':
#     make_rcfe.connect(bet_fmri_node, 'mask_file', bias_correction_node, 'mask_image')
#     make_rcfe.connect(bet_fmri_node, 'out_file', bias_correction_node, 'input_image')
#     # full_process.connect(make_rcfe, 'bet_fmri.out_file', get_transforms, 'fmri_to_temp.input_image')
#     # fullprocess.connect(bias_correction_node, 'output_image', get_transforms, 'fmri_to_temp.input_image')
#     #NEW
#     # make_rcfe.connect(bias_correction_node, 'output_image', make_rcfe, 'rcfe.input_image')
#     make_rcfe.connect(bias_correction_node, 'output_image', rcfe_node, 'input_image')
#     print('true facts')
# else:
#     make_rcfe.connect(mean_fmri_node, 'out_file', rcfe_node, 'input_image') #TODO: uncomment this, and disconect N4bias from rcfe node later





get_transforms = Workflow(name="get_transforms")
get_transforms.connect([(warp_to_152_node, merge_transforms_node, [('affine_transformation', 'in2'), ('warp_field', 'in1')])])
get_transforms.connect(merge_transforms_node, 'out', coreg_to_template_space_node, 'transforms')


full_process = Workflow(name='full_process')

# full_process.connect(accept_input, 'input_handler.time_series', make_rcfe, 'mcflirt.in_file')
full_process.connect(get_transforms, 'coreg_to_template_space.output_image', iso_smooth_node, 'in_file')
# warp_to_152_node.inputs.reference_image = template_image
# coreg_to_template_space_node.inputs.reference_image = template_image
'''
full_process.connect(accept_input, 'input_handler.time_series', make_rcfe, 'mcflirt.in_file')
'''
