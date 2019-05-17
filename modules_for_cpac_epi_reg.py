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

import cpac_epi_reg

ap = argparse.ArgumentParser()
ap.add_argument('-m', '--mean', required=False, help='The mean image you want to generate trasnforms from')
# ap.add_argument('-im', '--images', required=False, help='The derivative images you want the transfroms applied to')
ap.add_argument('-t', '--template', required=True, help='The template that the mean image is applied to to create transforms')
ap.add_argument('-b', '--bias', required=False, help='The bias mask image to be used wiht the mean image in N4 bias correction')
group = ap.add_mutually_exclusive_group(required=True)
group.add_argument('-i', '--images', nargs='+', help='The derivative images you want the transfroms applied to')
group.add_argument('-dt', '--derivatives', help='The text file containg the derivate path templates')
ap.add_argument('-d', '--directory', required=False, help='The directory to searchh for subject, session pairs')
ap.add_argument('-r', '--results_dir', required=True, help='where to store the results')
# ap.add_argument('-dt', '--derivatives', required=True, help='The text file containg the derivate path templates')
ap.add_argument('-ta', '--template_arguments', nargs='*', required=False, help='Associate the variables from your templates with a data source containing each variables values. Should be in the format: Key1 Source1 Key2 Source2 ...')
ap.add_argument('-p', '--processes', required=False, default=5, type=int, help='How many processes you want to dedicate to this task. Default 5')
ap.add_argument('-g', '--show_graphs', default=False, required=False, help='Do you want to have the workflow graphs written out? Default: False')
parsed_args, unknown = ap.parse_known_args()
args = vars(parsed_args)



wf = Workflow(name='extras')

merge_node = Node(Node(Merge(2, dimension='t'),  name='merge_transforms'))

wf.connect(cpac_epi_reg.transform_images.map_apply_node, 'output_image', merge_node, 'in_files')

cpac_epi_reg.transform_images