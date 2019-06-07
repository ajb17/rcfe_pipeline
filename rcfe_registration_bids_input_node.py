import os
from os.path import abspath
from nipype import Node

import argparse

from nipype.interfaces.io import BIDSDataGrabber
from bids import BIDSLayout


import rcfe_registration_config as config



ap = argparse.ArgumentParser()
ap.add_argument('-sub', '--subject', required=False, help='You can specify a single subject to analyze here')
ap.add_argument('-subs', '--subjects', required=False, help='An iterable source containing all the subjects to analyze (a text file for now)')

group = ap.add_mutually_exclusive_group(required=False)
group.add_argument('-t1_temp', '--t1_temp', help='The path to the template you are fitting your images to')
group.add_argument('-epi_temp', '--epi_temp', help='The path the a premade template that can fit an fmri time series to a structural space')

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
#TODO: make sure no crash occurs when using the general acq,task, ... params and only the epi registration route


ap.add_argument('-all', '--show_all', required=False, help='Write out all intermediate files')
#TODO: implement the functionoality to go with this

ap.add_argument('-r', '--results_dir', required=False, help='The directory that you want to write results to')
ap.add_argument('-p', '--processes', required=False, type=int, default=5, help='The amount of processes you want to dedicate to the process')
ap.add_argument('-g', '--draw_graphs', required=False, default='True', type=bool, help='Wether you want to have the graphs drawn out or not')
ap.add_argument('-b', '--bias_correction', required=False, default='True', help="Wether you want the N4 bias correction step or not ...")

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

#TODO: ___________ this is important if you want the other setup of the pipline, and I think it has to occur before importing setup
if args['t1_temp'] is not None:
    config.registration = config.Reg.t1
if args['epi_temp'] is not None:
    config.registration = config.Reg.epi
if args['results_dir'] is not None:
    config.results_directory = args['results_dir']
config.set_draw_graphs(args['draw_graphs'])
if args['bias_correction'] == 'False':
    config.set_bias_correction(False)

import rcfe_registration_node_setup

from rcfe_registration_node_setup import full_process
from rcfe_registration_node_setup import input_handler_node
from rcfe_registration_node_setup import accept_input

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


accept_input.connect([(data_grabber_node, input_handler_node, [('time_series', 'time_series'), ('struct', 'struct')])])

if config.registration.name == 't1':
    template_image = os.path.abspath(args['t1_temp'])
else:
    template_image = os.path.abspath(args['epi_temp'])

rcfe_registration_node_setup.set_template_image(template_image)#, config.Reg.t1)

# a = data_grabber_node.run()
full_process.run('MultiProc', plugin_args={'n_procs':args['processes']})



