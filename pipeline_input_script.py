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

import _rcfe_registration_pipeline as rp

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
#TODO: I think that ardgparse might read my False as "False", so i had to manually change the default here to get my test working
args = vars(ap.parse_args())


rp.args = args


# set up data grabbing node using any of Nipype's datagrabbing interfaces
bids = False
if bids:
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
    data_grabber_node = Node(BIDSDataGrabber(), 'data_grabber')
    data_grabber_node.inputs.base_dir = args['directory']
    data_grabber_node.inputs.output_query = query



    if args['subject'] is not None:
        # file_grabber.iterables = ('subject', layout.get_subjects())#file_grabber.inputs.subject = 'M10999905'#args['subject']
        data_grabber_node.iterables = ('subject', [args['subject']])
        #file_grabber.inputs.subject = args['subject']
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

    #if not args.has_key('session') and not:

    #TODO: handle the subjects that dont have the specific session somehiwm i think they are causing jsut edning with a crash rn
    # also, there are result files created for these failed iterations rn, but theres no point to the
    data_grabber_node.inputs.raise_on_empty = False#True



else:
    # data_grabber_node = Node(DataGrabber)

    data_grabber_node = Node(DataGrabber(base_directory=args['directory'], sort_filelist=True, raise_on_empty=False, outfields=['time_series', 'struct'], infields=['sub']), name='data_grabber')
    data_grabber_node.inputs.template = '*'
    data_grabber_node.inputs.raise_on_empty = False#True
    data_grabber_node.inputs.drop_blank_outputs = True
    # /projects/stan/goff/recon/TYY-%s/ep2d_bold_TR_300_REST.nii
    data_grabber_node.inputs.field_template = dict(time_series='/projects/stan/goff/recon/TYY-%s/ep2d_bold_TR_300_REST.nii', struct='/projects/stan/goff/recon/TYY-%s/t1_to_mni.nii.gz')
    subs = [i[0:i.find(',')] for i in open('/projects/abeetem/goff_data/goff_data_key.csv', 'r')][2:]
    print('\n\n')
    data_grabber_node.inputs.template_args['struct'] =  [['sub']]
    data_grabber_node.inputs.template_args['time_series'] = [['sub']]
    data_grabber_node.iterables = [('sub', subs)]
    print('\n\n\n\n')
    print(data_grabber_node.iterables)
    #[('sub', sub_list), ('ses', ses_list)

    #template = abspath(args['template'])



rp.accept_input.connect([(data_grabber_node, rp.input_handler_node, [('time_series', 'time_series'), ('struct', 'struct')])])


# Connect the data grabber node to the input handling node of the registratioin pipline
rp.full_process.connect()







