import nipype
import os
from os.path import abspath
from nipype import Workflow, Node, MapNode, Function

from nipype.interfaces.utility import Merge
from nipype.interfaces.ants import WarpImageMultiTransform, Registration, legacy, ApplyTransforms, N4BiasFieldCorrection
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
ap.add_argument('-d', '--directory', required=False, help='The directory to searchh for subject, session pairs')
ap.add_argument('-r', '--results_dir', required=True, help='where to store the results')
ap.add_argument('-der', '--derivatives', required=True, help='The text file containg the derivate path templates')
ap.add_argument('-iter', '--iterables', nargs='*', required=False, help='Associate the variables from your templates with a data source containing each variables values. Should be in the format: Key1 Source1 Key2 Source2 ...')
ap.add_argument('-p', '--processes', required=False, default=5, type=int, help='How many processes you want to dedicate to this task. Default 5')
parsed_args, unknown = ap.parse_known_args()
args = vars(parsed_args)


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
    ars[unicode(key)] = [[arg.rstrip('\n').lstrip(' ') for arg in targs if arg is not '']]#TODO: I wrapped this in a list for a reason, probably to match something in nipype, but should see if i can remove it, it complicates a few things down the road
    #TODO: this would probably be a little more efficient to do it as we create the list if possible

derivatives_names = temps.keys()
derivatives_names.remove('mean')
if 'bias_mask' in derivatives_names:
    derivatives_names.remove('bias_mask')

template = abspath(args['template'])


temp_args = args['iterables']
# This formats the above list into a dictionary where we can much more easily associate keywords to their lists
template_arguments = {temp_args[::2][i]: temp_args[1::2][i] for i in range(len(temp_args) / 2)} #TODO: is this dictionary comprehension too much?


data_grabber_node = Node(DataGrabber(base_directory=args['directory'], sort_filelist=True, raise_on_empty=False, infields=template_arguments.keys(), outfields=[tmp for tmp in temps]), name='data_grabber')
data_grabber_node.inputs.template = '*'
data_grabber_node.inputs.raise_on_empty = True
data_grabber_node.inputs.drop_blank_outputs = True
data_grabber_node.inputs.field_template = temps
data_grabber_node.inputs.template_args = ars
data_grabber_node.iterables = [ (  key,
                                   [thing.rstrip('\n') for thing in open(template_arguments[key], 'r')]
                                )
                                for key in template_arguments.keys()] #TODO: Is nested list comprehenion too much?
                                #[('sub', sub_list), ('ses', ses_list)]

bias_correction_node = Node(N4BiasFieldCorrection(), name='bias_correction')
generate_transforms_node = Node(legacy.GenWarpFields(reference_image=template), name='generate_transforms')
merge_transforms_node = Node(Merge(2), iterfield='in2', name='merge_transforms')


merge_input_files_node = Node(Merge(len(derivatives_names)), name='merge_input_files')

map_apply_node = MapNode(interface=ApplyTransforms(reference_image=template, interpolation='BSpline'), iterfield=['input_image'], name='map_apply_node')

transform_images = Workflow(name='cpac_epi_reg', base_dir=args['results_dir'])# base_dir='/projects/abeetem/results/cpac_epi_reg')

#TODO: do reho, res, bias mask are all hardcoded here, but they shouldnt be
if 'bias_mask' in temps:
    transform_images.connect([(data_grabber_node, bias_correction_node, [('bias_mask', 'mask_image')])])
    transform_images.connect([(data_grabber_node, bias_correction_node, [('mean', 'input_image')])])
    transform_images.connect([(bias_correction_node, generate_transforms_node, [('output_image', 'input_image')])])
else:
    #TODO: Should I print an indication that no bias mask was used? It didnt have much of an impact on the final results from what i could tell at least
    transform_images.connect([(data_grabber_node, generate_transforms_node, [('mean', 'input_image')])])
#TODO: the input images are by the input node, but the

transform_images.connect([(data_grabber_node, merge_input_files_node, [(derivatives_names[i], 'in' +str(i+1)) for i in range(len(derivatives_names))])])

transform_images.connect([(merge_input_files_node, map_apply_node, [('out', 'input_image')])])

transform_images.connect([(generate_transforms_node, merge_transforms_node, [('affine_transformation', 'in2'), ('warp_field', 'in1')])])
transform_images.connect(merge_transforms_node, 'out', map_apply_node, 'transforms')

data_sink_node = Node(nio.DataSink(base_directory=args['results_dir'] + 'output'), name='data_sink')
transform_images.connect(generate_transforms_node, 'output_file', data_sink_node, 'output_file')
transform_images.connect(map_apply_node, 'output_image', data_sink_node, 'output_image')


if True:
    transform_images.write_graph(graph2use='orig', dotfilename='./cpac_epi_reg_orig', format='svg')
    transform_images.write_graph(graph2use='colored', dotfilename='./cpac_epi_reg_colored', format='svg')
    transform_images.write_graph(graph2use='exec', dotfilename='./cpac_epi_reg_exec', format='svg')

# transform_images.run('MultiProc', plugin_args={'n_procs':6})
transform_images.run('MultiProc', plugin_args={'n_procs':args['processes']})
#TODO: The mean image and the bias mask are hard coded values, that must be specified in a text file and they must be name 'mean' and 'bias_mask" exaclty.
# I need to adjust the rigidity of this, ideally wihtout writing every possible 'bias_mask' 'BiasMask' combination, and wihtout having to create even more text files
# to hold each no derivative template.
