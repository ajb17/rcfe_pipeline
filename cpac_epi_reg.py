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


#from pipeline_plus import get_transforms

ap = argparse.ArgumentParser()
ap.add_argument('-s', '--starter', required=True, help='The image that is applied to the template to create transforms')
ap.add_argument('-t', '--template', required=True, help='The template that the starter image is applied to to create transforms')
group = ap.add_mutually_exclusive_group(required=True)
group.add_argument('-i', '--images', nargs='+', help='The images paths you want to have the transformations appplied to')
group.add_argument('-ips', '--image_path_source', help='An iterables source of image files paths to have transformations applied to')

args = vars(ap.parse_args())


# TODO: What is the input type for images?
# we should end up wiht a list of image paths at least

start_image = args['starter']
template = args['template']
if args['images'] is not None:
    image_paths = args['images']
elif args['image_path_source'] is not None:

    image_paths = args['image_path_source']
else:
    raise Exception("Should specify images as either a list of image paths, or an iterable source of image paths, such as a textfile")


generate_transforms_node = Node(legacy.GenWarpFields(input_image=start_image, reference_image=template), name='generate_transforms')
merge_transforms_node = Node(Merge(2), iterfield='in2', name='merge_transforms')
apply_transforms_node = Node(ApplyTransforms(reference_image=template, interpolation='BSpline'), iterables=('input_image', image_paths), name='apply_transform')



transform_images = Workflow(name='transform_images', base_dir='/projects/abeetem/results/transform_images')
transform_images.connect([(generate_transforms_node, merge_transforms_node, [('affine_transformation', 'in2'), ('warp_field', 'in1')])])
transform_images.connect(merge_transforms_node, 'out', apply_transforms_node, 'transforms')

transform_images.write_graph(graph2use='orig', dotfilename='./test_orig', format='svg')
transform_images.write_graph(graph2use='colored', dotfilename='./test_colored', format='svg')
transform_images.run()



















#
#
#
# file_grabber = Node(BIDSDataGrabber(), name="file_grabber")
# file_grabber.inputs.base_dir = args['directory']
# file_grabber.inputs.output_query = query
#
# # The BIDSDataGrabber outputs the files inside of a list, but all other nodes only accepts file paths, not lsits
# def unlist(time_series, struct):
#     print(struct)
#     return time_series[0], struct[0]
# file_unwrapper = Node(Function(function=unlist, output_names=['time_series', 'struct']), name='file_unwrapper')
#
#
#
#
# accept_input = Workflow(name='take_input')
# accept_input.connect([(file_grabber, file_unwrapper, [('time_series', 'time_series'), ('struct', 'struct')])])
#
# get_transforms = Workflow(name="get_transforms")
# reg_fmri_temp = Node(legacy.GenWarpFields(reference_image=template), name='fmri_to_temp')#Registration(fixed_image=template), name='fmri-to-temp')
#
# apply_epi_temp = Node(ApplyTransforms(reference_image=template, interpolation='BSpline'), name='apply_epi_transforms')
# merge_epi_transforms = Node(Merge(2), iterfield='in2', name='merge_epi')
# #get_transforms_epi = Workflow(name="get_transforms_epi")
# get_transforms.connect([(reg_fmri_temp, merge_epi_transforms, [('affine_transformation', 'in2'),  ('warp_field', 'in1')])])
# get_transforms.connect(merge_epi_transforms, 'out', apply_epi_temp, 'transforms')
#
# base_dir = os.path.abspath(base_dir_string)
# full_process = Workflow(name='full_process', base_dir=base_dir)
# full_process.connect(accept_input, 'file_unwrapper.time_series', make_rcfe, 'mcflirt.in_file')
#
# full_process.connect(make_rcfe, 'bet_fmri.out_file', get_transforms, 'fmri_to_temp.input_image')
# full_process.connect(make_rcfe, 'rcfe.output_image', get_transforms, 'apply_epi_transforms.input_image')
# full_process.connect(get_transforms, 'apply_epi_transforms.output_image', isoSmooth, 'in_file')
#
#
#
#
