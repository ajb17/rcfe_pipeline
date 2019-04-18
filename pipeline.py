# import sklearn
# import nilearn

import nipype
import os
from os.path import abspath
from nipype import Workflow, Node, MapNode, Function
# from nilearn.plotting import plot_anat

# import matplotlib.pyplot as plt

from nipype.interfaces.fsl import MCFLIRT, maths, BET, FLIRT
from nipype.interfaces.fsl.maths import MeanImage, IsotropicSmooth
from nipype.interfaces.utility import Merge
from nipype.interfaces.afni import SkullStrip
from nipype.interfaces.ants import WarpImageMultiTransform, Registration, legacy, ApplyTransforms
import argparse
import nibabel as nib
from scipy import stats

import numpy as np
# from nipype.scripts.crash_files import display_crash_file
import nipype.interfaces.io as nio
from nipype.interfaces.io import BIDSDataGrabber
from bids import BIDSLayout



ap = argparse.ArgumentParser()
ap.add_argument('-sub', '--subject', required=False, help='You can specify a single subject to analyze here')

group = ap.add_mutually_exclusive_group(required=True)
group.add_argument('-t1_temp', '--t1_temp', help='The path to the template you are fitting your images to')
group.add_argument('-epi_temp', '--epi_temp', help='The path the a premade template that can fit an fmri time series to a structural space')

#ap.add_argument('-temp', '--temp', required=True, help='The path to the template you are fitting your images to')
ap.add_argument('-d', '--directory', required=True, help='The directory that your subjects are all found in')
ap.add_argument('-t-ses', '--t1-session', required=False, help='The specific session you are looking for for t1 images')
ap.add_argument('-t-acq', '--t1-acquisition', required=False, help='The acquisition to look for in T1 images')
ap.add_argument('-t-task', '--t1-task', required=False, help='The task to look for in T1 images')
ap.add_argument('-f-ses', '--fmri-session', required=False, help='The session to look for in the fmri time series')
ap.add_argument('-f-acq', '--fmri-acquisition', required=False, help='The acquisition for fmri time series')
ap.add_argument('-f-task', '--fmri-task', required=False, help='The task to look for in fmri time series')

ap.add_argument('-ses', '--session', required=False, help='The session to look for in both T1 and fmri files')
ap.add_argument('-acq', '--acquisition', required=False, help='The acquisition to look for in both T1 and fmri files')
ap.add_argument('-task', '--task', required=False, help='The task to look for in both T1 and fmri files')


args = vars(ap.parse_args())


time_series_params = {"datatype": "func", "extensions": ["nii", ".nii.gz"]}
struct_params = {"datatype": "anat", "suffix": "T1w", "extensions": ["nii", ".nii.gz"]}


if args['task'] is not None:
    struct_params['task'] = args['task']
    time_series_params['task'] = args['task']

else:
    if args['fmri_task'] is not None:
        time_series_params['task'] = args['fmri_task']

    if args['t1_task'] is not None:
        struct_params['task'] = args['t1_task']

if args['acquisition'] is not None:
    struct_params['acquisition'] = args['acquisition']
    time_series_params['acquisition'] = args['acquisition']
else:
    if args['t1_acquisition'] is not None:
        struct_params['acquisition'] = args['t1_acquisition']
    if args['fmri_acquisition'] is not None:
        time_series_params['acquisition'] = args['fmri_acquisition']
if args['session'] is not None:
    struct_params['session'] = args['session']
    time_series_params['session'] = args['session']
else:
    if args['t1_session'] is not None:
        struct_params['session'] = args["t1_session"]
    if args['fmri_session'] is not None:
        time_series_params['session'] = args['fmri_session']


query = { 'time_series' : time_series_params, 'struct' : struct_params}

layout = BIDSLayout(args['directory'])

#TODO: eliminate search paths before files are created and resoruces are wasted



file_grabber = Node(BIDSDataGrabber(), name="file_grabber")
file_grabber.inputs.base_dir = args['directory']
file_grabber.inputs.output_query = query


if args['subject'] is not None:
   # file_grabber.iterables = ('subject', layout.get_subjects())#file_grabber.inputs.subject = 'M10999905'#args['subject']
    file_grabber.iterables = ('subject', [args['subject']])
    #file_grabber.inputs.subject = args['subject']
else:
    file_grabber.iterables = ('subject', layout.get_subjects())

#if not args.has_key('session') and not:

#TODO: handle the subjects that dont have the specific session somehiwm i think they are causing jsut edning with a crash rn
# also, there are result files created for these failed iterations rn, but theres no point to the
file_grabber.inputs.raise_on_empty = True

# The BIDSDataGrabber outputs the files inside of a list, but all other nodes only accepts file paths, not lsits
def unlist(time_series, struct):
    print(struct)
    return time_series[0], struct[0]
file_unwrapper = Node(Function(function=unlist, output_names=['time_series', 'struct']), name='file_unwrapper')


"""
Inputs:
1) fMRI timeseries
2) T1 Structural Image
3) template image

processing:
1) motion correction (mcflrt);
    compute mean (fslmaths);
    skull strip (BET);
    scaling within mask: zscale (python code or fslstats + fslmaths),multiply by -1 = rcFe;                              # AvScale???  Slicer???
    coregister mean fMRI to skullstripped T1 (FLIRT)    60oF     -> image, mat file

2) skull strip (afni 3dSkullStrip);
    warp whole head (not skull stripped) T1 to MNI 152 T1 2mm template (ANTS).
                                                                                   -> mat file/txt, image and coff file
3) apply combined coregistration from fMRI to T1 to MNI Template to rcFe (ANTS);
    apply spatial smoothing (4mm iso gaussian; fslmaths).
"""

if args['t1_temp'] is not None:
    template = os.path.abspath(args['t1_temp'])
else:
    template = os.path.abspath(args['epi_temp'])
    #template = ""
    print("set up other temp")

# 1_______________________
# Motion correction on fmri time series
mcflirt = Node(MCFLIRT(mean_vol=True, output_type='NIFTI'), name="mcflirt")


# Compute mean(fslmaths) of the fmri time series
mean_fmri = Node(MeanImage(output_type='NIFTI'), name="meanimage")

# Skull Strip the fmri time series
bet_fmri = Node(BET(output_type='NIFTI', mask=True), name="bet_fmri")

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
rcfe = Node(Function(input_names=['input_image', 'mask_image'], output_names=['output_image'], function=compute_scFe),
            name="rcfe")

# coregister (skullstripped) mean of the fmri time series to the skull stripped T1 structural
flirt = Node(FLIRT(dof=6), name="flirt", cost='mutualinfo')  # do i have to specify out_matrix_file???

# 2_____________________
# skullstrip the T1 structural image
skullstrip_structural = Node(SkullStrip(outputtype='NIFTI'), name='skullstrip')


# process_timeseries.connect(imagestats,'out_file', skullstrip, 'in_file')

# Warp whole head T1 Structural Image to MNI 152 template
warp_to_152 = Node(legacy.GenWarpFields(reference_image=template, similarity_metric="CC"), name="warp152")


# 3______________________
# coreg_to_struct_space = Node(FLIRT(apply_xfm=True, reference=struct_image, interp="sinc"), name="coreg")
coreg_to_struct_space = Node(FLIRT(apply_xfm=True, interp="sinc"), name="coreg_to_struct_space")

coreg_to_template_space = Node(ApplyTransforms(reference_image=template), name="coreg_to_template_space")
merge_transforms_node = Node(Merge(2), iterfield=['in2'], name="merge")

# Spatial smoothing
isoSmooth = Node(IsotropicSmooth(fwhm=4, output_type="NIFTI"), name='isoSmooth')

dataSink = Node(nio.DataSink(base_directory="results_dir", container='warp152_output', infields=['tt']),
                name='dataSink')


# Default process

base_dir = os.path.abspath("/projects/abeetem/results")#"fmriPipeline")
if args['epi_temp'] is not None:
    base_dir = os.path.abspath('/projects/abeetem/results2')
process_timeseries = Workflow(name="process_timeseries"
                              , base_dir=base_dir)
'''
process_timeseries.connect([
                            (file_grabber, file_unwrapper, [('time_series', 'time_series'), ('struct', 'struct')]),
                            (file_unwrapper, mcflirt, [('time_series', 'in_file')]),
                            (file_unwrapper, skullstrip_structural, [('struct', 'in_file')]),
                            (file_unwrapper, warp_to_152, [('struct', 'input_image')]),
                            (file_unwrapper, coreg_to_struct_space, [('struct', 'reference')]),

                            # Motion correct the input fmri time series, the produce the mean image
                            (mcflirt, mean_fmri, [('out_file', 'in_file')]),
                            # Skull strip the mean image
                            (mean_fmri, bet_fmri, [('out_file', 'in_file')]),
                            # Get the rcfe of the mean image, using the skullstripped mask
                            (mean_fmri, rcfe, [('out_file', 'input_image')]),
                            (bet_fmri, rcfe, [('mask_file', 'mask_image')]),
                            # Coregister the skullstripped fmri image to the T1 space, use the transformation matrix
                            # to coregister the skullstripped fmri image to the T1 space
                            (bet_fmri, flirt, [('out_file', 'in_file')]),
                            (skullstrip_structural, flirt, [('out_file', 'reference')]),
                            (flirt, coreg_to_struct_space, [('out_matrix_file', 'in_matrix_file')]),
                            # Transform the rcfe to the T1 space
                            (rcfe, coreg_to_struct_space, [('output_image', 'in_file')]),
                            # Transform the T1 structural image to the template space, use transform files to transform
                            # the T1 coregistered rcfe image to the template space
                            (warp_to_152, merge_transforms_node, [('affine_transformation', 'in2')]),
                            (warp_to_152, merge_transforms_node, [('warp_field', 'in1')]),
                            (merge_transforms_node, coreg_to_template_space, [('out', 'transforms')]),
                            # Transform the T1 coregistered rcfe image to the template space
                            (coreg_to_struct_space, coreg_to_template_space, [('out_file', 'input_image')]),
                            # Apply spatial smoothing to the template registered rcfe image
                            (coreg_to_template_space, isoSmooth, [('output_image', 'in_file')]),

                            # Write out intermediate files
                            (warp_to_152, dataSink, [('output_file', 'warp152')]),
                            (flirt, dataSink, [('out_file', 'flrt')])])
'''
# import pygraphviz
#process_timeseries.write_graph(graph2use='orig', dotfilename='./graph_origB.dot', format='svg')

# flirt.save()
# warp152.save()
# warp_to_152.get_output('output_file')
#process_timeseries.run('MultiProc', plugin_args={'n_procs':20})




accept_input = Workflow(name='take_input')
accept_input.connect([(file_grabber, file_unwrapper, [('time_series', 'time_series'), ('struct', 'struct')])])

#determine template type

#get rcfe_
make_rcfe = Workflow(name='make_rcfe')
###make_rcfe.connect(accept_input, 'file_unwrapper.time_series', mcflirt, 'in_file')
make_rcfe.connect(mcflirt, 'out_file', mean_fmri, 'in_file')
make_rcfe.connect(mean_fmri, 'out_file', bet_fmri, 'in_file')
make_rcfe.connect(mean_fmri, 'out_file', rcfe, 'input_image')
make_rcfe.connect(bet_fmri, 'mask_file', rcfe, 'mask_image')




#get fmri to template space
#get_transforms_output = Node()
get_transforms_t1 = Workflow(name="get_transforms_t1")
### get_transforms.connect(accept_input, 'file_unwrapper.struct', warp_to_152, 'input_image')
### get_transforms.connect(accept_input, 'file_unwrapper.struct', skullstrip_structural, 'in_file')
### get_transforms.connect(accept_input, 'file_unwrapper.struct', coreg_to_struct_space, 'reference')

get_transforms_t1.connect(skullstrip_structural, 'out_file', flirt, 'reference')
### get_transforms.connect(make_rcfe, 'bet_fmri.out_file', flirt, 'in_file')

get_transforms_t1.connect(flirt, 'out_matrix_file', coreg_to_struct_space, 'in_matrix_file')
### get_transforms.connect(make_rcfe, 'rcfe.output_image', coreg_to_struct_space, 'in_file')
get_transforms_t1.connect(coreg_to_struct_space, 'out_file', coreg_to_template_space, 'input_image')
#get_transforms.connect(accept_input, 'file_unwrapper.struct', warp_to_152, 'input_image')
get_transforms_t1.connect([(warp_to_152, merge_transforms_node, [('affine_transformation', 'in2'), ('warp_field', 'in1')])])
get_transforms_t1.connect(merge_transforms_node, 'out', coreg_to_template_space, 'transforms')



# Second processsing Option
reg_fmri_temp = Node(legacy.GenWarpFields(reference_image=template), name='fmri_to_temp')#Registration(fixed_image=template), name='fmri-to-temp')
apply_epi_temp = Node(ApplyTransforms(reference_image=template), name='bet_epi_to_temp')
merge_epi_transforms = Node(Merge(2), iterfield='in2', name='merge_epi')
get_transforms_epi = Workflow(name="get_transforms_epi")
get_transforms_epi.connect([(reg_fmri_temp, merge_epi_transforms, [('affine_transformation', 'in2'),  ('warp_field', 'in1')])])
get_transforms_epi.connect(merge_epi_transforms, 'out', apply_epi_temp, 'transforms')

# smooth_rcfe = Workflow(name='smooth rcfe')
# smooth_rcfe.connect()

default_temp=True
'''
fmri_to_template = Workflow(name='fmri_to_template')
if default_temp:
    fmri_to_template.connect(make_rcfe, 'rcfe.output_image', isoSmooth, 'in_file')
else:
    fmri_to_template.connect(get_transforms, 'coreg_to_template_space.output_image', isoSmooth, 'in_file')
'''


# process = Workflow(name='process')
# process.connect(make_rcfe, 'rcfe.output_image',)

#fmri_to_template.run()
#fmri_to_template.write_graph(graph2use='orig', dotfilename='./multiflow.dot', format='svg')

full_process = Workflow(name='full_process')
full_process.connect([(accept_input, mcflirt, [('file_unwrapper.time_series', 'in_file')]),
                      (make_rcfe, flirt, [('bet_fmri.out_file', 'in_file')]),
                      (make_rcfe, coreg_to_struct_space, [('rcfe.output_image', 'in_file')]),
                      (accept_input, warp_to_152, [('file_unwrapper.struct', 'input_image')]),
                      (accept_input, skullstrip_structural, [('file_unwrapper.struct', 'in_file')]),
                      (accept_input, coreg_to_struct_space, [('file_unwrapper.struct', 'reference')])
                     ])




if args['epi_temp'] is not None:
    # Is it the input fmri file or the mean image produced from it???
    full_process.connect(accept_input, 'file_unwrapper.time_series', reg_fmri_temp, 'input_image')
    #full_process.connect([(reg_fmri_temp, merge_epi_transforms, [('affine_transformation', 'in2'),  ('warp_field', 'in1')])])
    #full_process.connect(merge_epi_transforms, 'out', apply_epi_temp, 'transforms')
    full_process.connect(make_rcfe, 'rcfe.output_image', apply_epi_temp, 'input_image')
    full_process.connect(apply_epi_temp, 'output_image', isoSmooth, 'in_file')


    # full_process.connect(make_rcfe, 'rcfe.output_image', reg_fmri_temp, 'fixed_image')
    # full_process.connect(reg_fmri_temp, 'warped_image', isoSmooth, 'in_file')
    print('used other template')

else:

    full_process.connect(get_transforms_t1, 'coreg_to_template_space.output_image', isoSmooth, 'in_file')
    print('used default template')


full_process.run()
# full_process.write_graph(graph2use='colored', dotfilename='./full_process_graph_colored_shortcut', format='svg')
# full_process.disconnect(make_rcfe, 'rcfe.output_image', isoSmooth, 'in_file')
# full_process.connect(get_transforms, 'coreg_to_template_space.output_image', isoSmooth, 'in_file')
#full_process.write_graph(graph2use='colored', dotfilename='./full_process_graph_colored_default', format='svg')
full_process.write_graph(graph2use='colored', dotfilename='./full_process_graph_colored_other', format='svg')
