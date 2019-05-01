import nipype
import os
from os.path import abspath
from nipype import Workflow, Node, MapNode, Function
# from nilearn.plotting import plot_anat

# import matplotlib.pyplot as plt

from nipype.interfaces.utility import Merge
from nipype.interfaces.ants import WarpImageMultiTransform, Registration, legacy, ApplyTransforms
import argparse

import numpy as np
import nipype.interfaces.io as nio

from nipype import DataGrabber

ap = argparse.ArgumentParser()
ap.add_argument('-s', '--starter', required=False, help='The image that is applied to the template to create transforms')
ap.add_argument('-t', '--template', required=True, help='The template that the starter image is applied to to create transforms')
group = ap.add_mutually_exclusive_group(required=False)
group.add_argument('-i', '--images', nargs='+', help='The images paths you want to have the transformations appplied to')
group.add_argument('-ips', '--image_path_source', help='An iterables source of image files paths to have transformations applied to')
ap.add_argument('-sub_list', '--sub_list', required=False, help='The list of subjects to iterate through')
ap.add_argument('-ses_list', '--ses_list', required=False, help='The list of sessions to itereate through')
ap.add_argument('-d', '--directory', required=False, help='The directory to searchh for subject, session pairs')
ap.add_argument('-r', '--results_dir', required=True, help='where to store the results')
ap.add_argument('-der', '--derivatives', required=True, help='The text file containg the derivate path templates')
args = vars(ap.parse_args())


# TODO: What is the input type for images?
# we should end up wiht a list of image paths at least

# This creates the templates and template arguments that are accepted by Nipype's data grabber
def parse_template_entry(entry):
    key = entry[:min(entry.find(' '), entry.find('='))]
    first_quote_index = entry.find('"')
    second_quote_index = entry.find('"', first_quote_index+1)
    template = entry[first_quote_index+1: second_quote_index]
    args = [arg for arg in entry[second_quote_index+1:].split(',') if arg is not '']
    return key, template, args

# This is where we build up the dictionaries of templates and arguments for the nipype data grabber
temps = {}
ars = {}
for i in open(args['derivatives'], 'r'):
    if i is '' or i == '\n':
        continue
    key, temp, targs = parse_template_entry(i)
    temps[key] = temp.rstrip("\n")
    ars[unicode(key)] = [[arg.rstrip('\n').lstrip(' ') for arg in targs if arg is not '']]
    #TODO: this would probably be a little more efficient to do it as we create the list if possible



template = abspath(args['template'])


if args['sub_list'] is not None:
    if args['ses_list'] is None:
        raise Exception('Must specify ses_list if sub_list is specified')
    sub_list = args['sub_list']
    ses_list = args['ses_list']
sub_list = [sub.rstrip('\n') for sub in open(args['sub_list'], 'r')]
ses_list = [ses.rstrip('\n') for ses in open(args['ses_list'], 'r')]

#input_node = Node(Function(output_names=['mean', 'res', 'reho'], function=path_generator), iterables=[('sub', sub_list), ('ses', ses_list)], name='input_node')

def print_inputs(mean, res, reho):
    print('hello', mean, res, reho)
print_node = Node(Function(function=print_inputs), name='print_inputs')


data_grabber_node = Node(DataGrabber(base_directory=args['directory'], sort_filelist=True, raise_on_empty=False, infields=['sub', 'ses'], outfields=['mean', 'reho', 'res_filt']), name='data_grabber')
data_grabber_node.inputs.template = '*'
data_grabber_node.inputs.raise_on_empty = True
data_grabber_node.inputs.drop_blank_outputs = True
data_grabber_node.inputs.field_template = temps
data_grabber_node.inputs.template_args = ars
data_grabber_node.iterables = [('sub', sub_list), ('ses', ses_list)]


generate_transforms_node = Node(legacy.GenWarpFields(reference_image=template), name='generate_transforms')

merge_transforms_node = Node(Merge(2), iterfield='in2', name='merge_transforms')


#apply_transforms_node = Node(ApplyTransforms(reference_image=template, interpolation='BSpline'), iterables=, name='apply_transform')

merge_input_files_node = Node(Merge(2), iterfield='in2', name='merge_input_files')
#merge_input_files_node = Node(Merge(3), iterfield=['in2', 'in3'], name='merge_input_files')

map_apply_node = MapNode(interface=ApplyTransforms(reference_image=template, interpolation='BSpline'), iterfield=['input_image'], name='map_apply_node')

transform_images = Workflow(name='cpac_epi_reg',base_dir=args['results_dir'])# base_dir='/projects/abeetem/results/cpac_epi_reg')

transform_images.connect([(data_grabber_node, generate_transforms_node, [('mean', 'input_image')])])
#TODO: the input images are by the input node, but the

#transform_images.connect([(data_grabber_node, merge_input_files_node, [('reho', 'in1'), ('res_filt', 'in2'), ('mean', 'in3')])])
transform_images.connect([(data_grabber_node, merge_input_files_node, [('reho', 'in1'), ('res_filt', 'in2')])])


# transform_images.connect([(merge_input_files_node, apply_transforms_node, [('out', 'input_image')])])
transform_images.connect([(merge_input_files_node, map_apply_node, [('out', 'input_image')])])


# transform_images.connect([(input_node, apply_transforms_node, [('reho', 'input_image')])]) #TODO: not just reho later

transform_images.connect([(generate_transforms_node, merge_transforms_node, [('affine_transformation', 'in2'), ('warp_field', 'in1')])])
#transform_images.connect(merge_transforms_node, 'out', apply_transforms_node, 'transforms')
transform_images.connect(merge_transforms_node, 'out', map_apply_node, 'transforms')

if True:
    data_sink_node = Node(nio.DataSink( base_directory='/projects/abeetem/results/cpac_epi_reg6/data_sink'), name='data_sink')
    transform_images.connect(generate_transforms_node, 'output_file', data_sink_node, 'output_file')
    transform_images.connect(map_apply_node, 'output_image', data_sink_node, 'output_image')


if True:
    transform_images.write_graph(graph2use='orig', dotfilename='./cpac_epi_reg_orig', format='svg')
    transform_images.write_graph(graph2use='colored', dotfilename='./cpac_epi_reg_colored', format='svg')
    transform_images.write_graph(graph2use='exec', dotfilename='./cpac_epi_reg_exec', format='svg')

transform_images.run('MultiProc', plugin_args={'n_procs':6})

"""
Input mean image: 
/projects/cgutierrez/rockland_sample_cpac/All_Outputs/M10936246_DS2/mean_functional/_scan_rest_acq/1400/sub-M10936246_ses-DS2_task-rest_acq1400_bold_calc_resample_volreg_calc_tstat.nii.gz

apply transforms to these:
/projects/cgutierrez/rockland_sample_cpac/All_Outputs/M10936246_DS2/alff_img/_scan_rest_acq-1400/_compcor_ncomponents_5_selector_pc10.linear1.wm0.global1.motion1.quadratic1.gm0.compcor1.csf0/_hp_0.01/_lp_0.1/residual_filtered_3dT.nii.gz

/projects/cgutierrez/rockland_sample_cpac/All_Outputs/10936246_DS2/raw_reho_map/_scan_rest_acq-1400/_compcor_ncomponents_5_selector_pc10.linear1.wm0.global1.motion1.quadratic1.gm0.compcor1.csf0/_bandpass_freqs_0.01.10.0/ReHo.nii.gz
"""
