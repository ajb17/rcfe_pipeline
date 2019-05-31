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



ap = argparse.ArgumentParser()
ap.add_argument('-sub', '--subject', required=False, help='You can specify a single subject to analyze here')

group = ap.add_mutually_exclusive_group(required=False)
group.add_argument('-t1_temp', '--t1_temp', help='The path to the template you are fitting your images to')
group.add_argument('-epi_temp', '--epi_temp', help='The path the a premade template that can fit an fmri time series to a structural space')

#ap.add_argument('-temp', '--temp', required=True, help='The path to the template you are fitting your images to')
ap.add_argument('-d', '--directory', required=True, help='The directory that your subjects are all found in')
#TODO: i dont think we need any of these t1 parameters when we ust do the epi to template registration, so we have make these a mutually exclusive group somehwo

ap.add_argument('-t-ses', '--t1-session', required=False, help='The specific session you are looking for for t1 images')
ap.add_argument('-t-acq', '--t1-acquisition', required=False, help='The acquisition to look for in T1 images')
ap.add_argument('-t-task', '--t1-task', required=False, help='The task to look for in T1 images')
ap.add_argument('-f-ses', '--fmri-session', required=False, help='The session to look for in the fmri time series')
ap.add_argument('-f-acq', '--fmri-acquisition', required=False, help='The acquisition for fmri time series')
ap.add_argument('-f-task', '--fmri-task', required=False, help='The task to look for in fmri time series')

ap.add_argument('-ses', '--session', required=False, help='The session to look for in both T1 and fmri files')
ap.add_argument('-acq', '--acquisition', required=False, help='The acquisition to look for in both T1 and fmri files')
ap.add_argument('-task', '--task', required=False, help='The task to look for in both T1 and fmri files')
ap.add_argument('-all', '--show_all', required=False, help='Write out all intermediate files')

ap.add_argument('-subs', '--subjects', required=False, help='An iterable source containing all the subjects to analyze (a text file for now)')
ap.add_argument('-r', '--results_dir', required=False, help='The directory that you want to write results to')
ap.add_argument('-p', '--processes', required=False, type=int, default=5, help='The amount of processes you want to dedicate to the process')
ap.add_argument('-g', '--draw_graphs', required=False, default='False', type=bool, help='Wether you want to have the graphs drawn out or not')
ap.add_argument('-b', '--bias_correction', required=False, default='True', help="Wether you want the N4 bias correction step or not ...")
ap.add_argument('-test', '--test', required=False, default='False')

ap.add_argument('-ef', '--epi_images_format', required=False)
ap.add_argument('-tf', '--t1_image_format', required=False)
ap.add_argument('-tfa', '--t1_args', required=False)
ap.add_argument('-efa', '--epi_args', required=False)
#TODO: I think that ardgparse might read my False as "False", so i had to manually change the default here to get my test working
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


accept_input = Workflow(name='take_input')

# def unlist(time_series=None, struct=None):
#     #TODO: this type checking is a weird artifact of the wrapping done by the bids datagrabber. we should restructuer the code so that a value that is not already in a list doesnt even have to go throught this function
#     if type(time_series) is not list and type(struct) is not list:
#         return time_series, struct
#     return time_series[0], struct[0] #TODO: why the fisrt element only? is it a list wrapped list?

def handle_input_files(time_series=None, struct=None):
    if type(time_series) is not list and type(struct) is not list:
        return time_series, struct
    # The BIDSDatagrabber resulted in a list containing a list, this jsut remove the wrapping list
    return time_series[0], struct[0]
input_handler_node = Node(Function(function=handle_input_files, output_names=['time_series', 'struct']), name='input_handler')

if str(args['test']) != 'True':
    layout = BIDSLayout(args['directory'])

#TODO: eliminate search paths before files are created and resoruces are wasted


    file_grabber_node = Node(BIDSDataGrabber(), name="file_grabber")
    file_grabber_node.inputs.base_dir = args['directory']
    file_grabber_node.inputs.output_query = query


    if args['subject'] is not None:
        file_grabber_node.iterables = ('subject', [args['subject']])
    elif args['subjects'] is not None:
        def get_sub_from_path(path):
            if path.find('sub') == -1 or path.find('ses') == -1:
                return path
                #TODO: this is a temporary patch. need to refactor and direct to this function only if a path is given instead of a stad alone subject
            return path[path.find('sub-') + 4: path.find('/ses-')]
        #TODO: what if the subjects are given alone iwhtout a path
        sub_list = []
        for line in open(abspath(args['subjects']), 'r'):
            sub_list.append(get_sub_from_path(line).rstrip())
        file_grabber_node.iterables = ('subject', sub_list)
    else:
        file_grabber_node.iterables = ('subject', layout.get_subjects())


    #TODO: handle the subjects that dont have the specific session somehiwm i think they are causing jsut edning with a crash rn
    # also, there are result files created for these failed iterations rn, but theres no point to the
    file_grabber_node.inputs.raise_on_empty = False#True
    accept_input.connect([(file_grabber_node, input_handler_node, [('time_series', 'time_series'), ('struct', 'struct')])])
else:

    data_grabber_node = Node(DataGrabber(base_directory=args['directory'], sort_filelist=True, raise_on_empty=False, outfields=['time_series', 'struct'], infields=['sub']), name='data_grabber')
    data_grabber_node.inputs.template = '*'
    data_grabber_node.inputs.raise_on_empty = False#True
    data_grabber_node.inputs.drop_blank_outputs = True
    # /projects/stan/goff/recon/TYY-%s/ep2d_bold_TR_300_REST.nii
    #TODO: Hardcoded

    # time_series_format = '/projects/stan/goff/recon/TYY-%s/ep2d_bold_TR_300_REST.nii'
    # struct_format = '/projects/stan/goff/recon/TYY-%s/t1_to_mni.nii.gz'
    time_series_format = args['t1_images_format']
    struct_format = args['epi_images_format']

    data_grabber_node.inputs.field_template = dict(time_series=time_series_format, struct=struct_format)
    subs = [i[0:i.find(',')] for i in open('/projects/abeetem/goff_data/goff_data_key.csv', 'r')][2:7]

    print('\n\n')
    data_grabber_node.inputs.template_args['struct'] =  [['sub']]
    data_grabber_node.inputs.template_args['time_series'] = [['sub']]
    data_grabber_node.iterables = [('sub', subs)]
    print('\n\n\n\n')
    print(data_grabber_node.iterables)
    accept_input.connect([(data_grabber_node, input_handler_node, [('time_series', 'time_series'), ('struct', 'struct')])])
    #[('sub', sub_list), ('ses', ses_list)

    #template = abspath(args['template'])

    '/projects/stan/goff/recon/TYY-Ndyx501a/ep2d_bold_TR_300_REST.nii'
    '/projects/stan/goff/recon/TYY-Ndyx501a/t1_to_mni.nii.gz'




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

# Motion correction on fmri time series
mcflirt_node = Node(MCFLIRT(mean_vol=True, output_type='NIFTI'), name="mcflirt")


# Compute mean(fslmaths) of the fmri time series
mean_fmri_node = Node(MeanImage(output_type='NIFTI'), name="meanimage")

# Skull Strip the fmri time series
bet_fmri_node = Node(BET(output_type='NIFTI', mask=True), name="bet_fmri")

# Bias Correct the fmri time series
bias_correction_node = Node(N4BiasFieldCorrection(), name='bias_correction')

if args['t1_temp'] is not None:
    template = os.path.abspath(args['t1_temp'])
else:
    template = os.path.abspath(args['epi_temp'])

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
warp_to_152_node = Node(legacy.GenWarpFields(reference_image=template, similarity_metric="CC"), name="warp152")


# coreg_to_struct_space = Node(FLIRT(apply_xfm=True, reference=struct_image, interp="sinc"), name="coreg")
coreg_to_struct_space_node = Node(FLIRT(apply_xfm=True, interp="sinc", cost='mutualinfo'), name="coreg_to_struct_space")

coreg_to_template_space_node = Node(ApplyTransforms(reference_image=template, interpolation='BSpline'), name="coreg_to_template_space")
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
if args['bias_correction'] is 'True':
    make_rcfe.connect(bet_fmri_node, 'mask_file', bias_correction_node, 'mask_image')
    make_rcfe.connect(bet_fmri_node, 'out_file', bias_correction_node, 'input_image')
    # full_process.connect(make_rcfe, 'bet_fmri.out_file', get_transforms, 'fmri_to_temp.input_image')
    # fullprocess.connect(bias_correction_node, 'output_image', get_transforms, 'fmri_to_temp.input_image')
    #NEW
    # make_rcfe.connect(bias_correction_node, 'output_image', make_rcfe, 'rcfe.input_image')
    make_rcfe.connect(bias_correction_node, 'output_image', rcfe_node, 'input_image')
    print('true facts')
else:
    make_rcfe.connect(mean_fmri_node, 'out_file', rcfe_node, 'input_image') #TODO: uncomment this, and disconect N4bias from rcfe node later



get_transforms = Workflow(name="get_transforms")
if args['t1_temp'] is not None:
    get_transforms.connect(skullstrip_structural_node, 'out_file', flirt_node, 'reference')
    ### get_transforms.connect(make_rcfe, 'bet_fmri.out_file', flirt, 'in_file')

    get_transforms.connect(flirt_node, 'out_matrix_file', coreg_to_struct_space_node, 'in_matrix_file')
    ### get_transforms.connect(make_rcfe, 'rcfe.output_image', coreg_to_struct_space, 'in_file')
    get_transforms.connect(coreg_to_struct_space_node, 'out_file', coreg_to_template_space_node, 'input_image')
    #get_transforms.connect(accept_input, 'file_unwrapper.struct', warp_to_152, 'input_image')
    get_transforms.connect([(warp_to_152_node, merge_transforms_node, [('affine_transformation', 'in2'), ('warp_field', 'in1')])])
    get_transforms.connect(merge_transforms_node, 'out', coreg_to_template_space_node, 'transforms')

else:
    # Second processsing Option
    #TODO: instead of giving the reference imageges immeeadly, we may want to pass them in from the file grabber for more clarity in the diagram
    reg_fmri_temp = Node(legacy.GenWarpFields(reference_image=template), name='fmri_to_temp')#Registration(fixed_image=template), name='fmri-to-temp')
    apply_epi_temp = Node(ApplyTransforms(reference_image=template, interpolation='BSpline'), name='apply_epi_transforms')
    merge_epi_transforms = Node(Merge(2), iterfield='in2', name='merge_epi')
    #get_transforms_epi = Workflow(name="get_transforms_epi")
    get_transforms.connect([(reg_fmri_temp, merge_epi_transforms, [('affine_transformation', 'in2'),  ('warp_field', 'in1')])])
    get_transforms.connect(merge_epi_transforms, 'out', apply_epi_temp, 'transforms')


# apply_transforms = Workflow(name='apply_transforms')
# if args['t1_temp'] is not None:

base_dir_string = args['results_dir']#"/projects/abeetem/results/pipelineplus"
if args['t1_temp'] is not None:
    base_dir_string = base_dir_string + '/t1_reg'
else:
    base_dir_string = base_dir_string + '/epi_reg'



base_dir = os.path.abspath(base_dir_string)
full_process = Workflow(name='full_process', base_dir=base_dir)

if args['t1_temp'] is not None:
    full_process.connect([(accept_input, make_rcfe, [('input_handler.time_series', 'mcflirt.in_file')]),
                      (make_rcfe, get_transforms, [('bet_fmri.out_file', 'flirt.in_file')]),
                      (make_rcfe, get_transforms, [('rcfe.output_image', 'coreg_to_struct_space.in_file')]),
                      (accept_input, get_transforms, [('input_handler.struct', 'warp152.input_image')]),
                      (accept_input, get_transforms, [('input_handler.struct', 'skullstrip.in_file')]),
                      (accept_input, get_transforms, [('input_handler.struct', 'coreg_to_struct_space.reference')]),
                     ])
    full_process.connect(get_transforms, 'coreg_to_template_space.output_image', iso_smooth_node, 'in_file')

else:
    full_process.connect(accept_input, 'input_handler.time_series', make_rcfe, 'mcflirt.in_file')
    #TODO: make this bias correctin optional
    if args['bias_correction'] is 'True':
        # full_process.connect(make_rcfe, 'bet_fmri.mask_file', bias_correction_node, 'mask_image')
        # full_process.connect(make_rcfe, 'bet_fmri.out_file', bias_correction_node, 'input_image')
        # # full_process.connect(make_rcfe, 'bet_fmri.out_file', get_transforms, 'fmri_to_temp.input_image')
        # full_process.connect(bias_correction_node, 'output_image', get_transforms, 'fmri_to_temp.input_image')
        full_process.connect(make_rcfe, 'bias_correction.output_image', get_transforms, 'fmri_to_temp.input_image')
    else:
        full_process.connect(make_rcfe, 'bet_fmri.out_file', get_transforms, 'fmri_to_temp.input_image')
    full_process.connect(make_rcfe, 'rcfe.output_image', get_transforms, 'apply_epi_transforms.input_image')
    full_process.connect(get_transforms, 'apply_epi_transforms.output_image', iso_smooth_node, 'in_file')



# full_process.run('MultiProc', plugin_args={'n_procs':args['processes']})


if str(args['draw_graphs']) == 'True':
    graph_name = args['results_dir'] +'/graphs/'
    if args['t1_temp'] is not None:
        full_process.write_graph(graph2use='colored', dotfilename=graph_name +'colored', format='svg')
    else:
        full_process.write_graph(graph2use='colored', dotfilename=graph_name + 'colored', format='svg')
        full_process.write_graph(graph2use='flat', dotfilename=graph_name + 'flat', format='svg')
else:
    print(args['draw_graphs'])
###
