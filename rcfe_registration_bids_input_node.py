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
import rcfe_registration_node_setup

from rcfe_registration_node_setup import full_process
from rcfe_registration_node_setup import get_transforms
from rcfe_registration_node_setup import make_rcfe
from rcfe_registration_node_setup import coreg_to_template_space_node
from rcfe_registration_node_setup import warp_to_152_node
from rcfe_registration_node_setup import coreg_to_struct_space_node
from rcfe_registration_node_setup import input_handler_node
from rcfe_registration_node_setup import merge_transforms_node
from rcfe_registration_node_setup import bias_correction_node
from rcfe_registration_node_setup import iso_smooth_node
from rcfe_registration_node_setup import flirt_node
from rcfe_registration_node_setup import mcflirt_node
from rcfe_registration_node_setup import data_sink_node
from rcfe_registration_node_setup import bet_fmri_node
from rcfe_registration_node_setup import mean_fmri_node
from rcfe_registration_node_setup import skullstrip_structural_node
from rcfe_registration_node_setup import rcfe_node
from rcfe_registration_node_setup import accept_input


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

ap.add_argument('-subs', '--subjects', required=False, help='An iterable source containing all the subjects to analyze (a text file for now)')

ap.add_argument('-all', '--show_all', required=False, help='Write out all intermediate files')

ap.add_argument('-r', '--results_dir', required=False, help='The directory that you want to write results to')
ap.add_argument('-p', '--processes', required=False, type=int, default=5, help='The amount of processes you want to dedicate to the process')
ap.add_argument('-g', '--draw_graphs', required=False, default='False', type=bool, help='Wether you want to have the graphs drawn out or not')
ap.add_argument('-b', '--bias_correction', required=False, default='True', help="Wether you want the N4 bias correction step or not ...")

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



layout = BIDSLayout(args['directory'])

#TODO: eliminate search paths before files are created and resoruces are wasted


data_grabber_node = Node(BIDSDataGrabber(), name="data_grabber")
data_grabber_node.inputs.base_dir = args['directory']
data_grabber_node.inputs.output_query = query


if args['subject'] is not None:
    data_grabber_node.iterables = ('subject', [args['subject']])
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
    data_grabber_node.iterables = ('subject', sub_list)
else:
    data_grabber_node.iterables = ('subject', layout.get_subjects())


#TODO: handle the subjects that dont have the specific session somehiwm i think they are causing jsut edning with a crash rn
# also, there are result files created for these failed iterations rn, but theres no point to the
data_grabber_node.inputs.raise_on_empty = False#True
# accept_input.connect([(data_grabber_node, input_handler_node, [('time_series', 'time_series'), ('struct', 'struct')])])

accept_input.connect([(data_grabber_node, input_handler_node, [('time_series', 'time_series'), ('struct', 'struct')])])


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
if args['t1_temp'] is not None:
    template_image = os.path.abspath(args['t1_temp'])
else:
    template_image = os.path.abspath(args['epi_temp'])
make_rcfe.connect(bet_fmri_node)
if args['bias_correction'] is 'True':
    make_rcfe.connect(bet_fmri_node, 'mask_file', bias_correction_node, 'mask_image')
    make_rcfe.connect(bet_fmri_node, 'out_file', bias_correction_node, 'input_image')
    #NEW;
    # make_rcfe.connect(bias_correction_node, 'output_image', make_rcfe, 'rcfe.input_image')
    make_rcfe.connect(bias_correction_node, 'output_image', rcfe_node, 'input_image')
    print('true facts')
else:
    make_rcfe.connect(mean_fmri_node, 'out_file', rcfe_node, 'input_image') #TODO: uncomment this, and disconect N4bias from rcfe node later




base_dir_string = args['results_dir']#"/projects/abeetem/results/pipelineplus"
if args['t1_temp'] is not None:
    base_dir_string = base_dir_string + '/t1_reg'
else:
    base_dir_string = base_dir_string + '/epi_reg'



base_dir = os.path.abspath(base_dir_string)
# full_process = Workflow(name='full_process', base_dir=base_dir)
full_process.base_dir = base_dir

full_process.connect(accept_input, 'input_handler.time_series', make_rcfe, 'mcflirt.in_file')
# full_process.connect(get_transforms, 'coreg_to_template_space.output_image', iso_smooth_node, 'in_file')

warp_to_152_node.inputs.reference_image = template_image
coreg_to_template_space_node.inputs.reference_image = template_image


if args['t1_temp'] is not None:
    import rcfe_registration_t1_pipeline
else:
    import rcfe_registration_epi_pipeline

# full_process.run('MultiProc', plugin_args={'n_procs':args['processes']})


if str(args['draw_graphs']) == 'True':
    graph_name = args['results_dir'] +'/graphs/'
    full_process.write_graph(graph2use='colored', dotfilename=graph_name + 'colored', format='svg')
    full_process.write_graph(graph2use='flat', dotfilename=graph_name + 'flat', format='svg')
###
full_process.run('MultiProc', plugin_args={'n_procs':args['processes']})

