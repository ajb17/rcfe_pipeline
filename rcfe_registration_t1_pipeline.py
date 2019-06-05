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

import rcfe_registration_config

# get_transforms.connect([(warp_to_152_node, merge_transforms_node, [('affine_transformation', 'in2'), ('warp_field', 'in1')])])
# get_transforms.connect(merge_transforms_node, 'out', coreg_to_template_space_node, 'transforms')

t1_wf = Workflow(name='t1')
t1_wf.connect(skullstrip_structural_node, 'out_file', flirt_node, 'reference')
t1_wf.connect(flirt_node, 'out_matrix_file', coreg_to_struct_space_node, 'in_matrix_file')

full_process.connect([
                  (make_rcfe, t1_wf, [('bet_fmri.out_file', 'flirt.in_file')]),
                  (make_rcfe, t1_wf, [('rcfe.output_image', 'coreg_to_struct_space.in_file')]),
                  (accept_input, get_transforms, [('input_handler.struct', 'warp152.input_image')]),
                  (accept_input, t1_wf, [('input_handler.struct', 'skullstrip.in_file')]),
                  (accept_input,t1_wf, [('input_handler.struct', 'coreg_to_struct_space.reference')]),
                  (t1_wf, get_transforms, [('coreg_to_struct_space.out_file', 'coreg_to_template_space.input_image')])
                 ])
# full_process.connect(t1_wf,'coreg_to_struct_space.out_file', get_transforms, 'coreg_to_template_space.input_image')



