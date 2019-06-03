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


    # full_process.connect(accept_input, 'input_handler.time_series', make_rcfe, 'mcflirt.in_file')
    #TODO: make this bias correctin optional
# if args['bias_correction'] is 'True':
bias_correction = True
if bias_correction:
    full_process.connect(make_rcfe, 'bias_correction.output_image', get_transforms, 'warp152.input_image')
else:
    full_process.connect(make_rcfe, 'bet_fmri.out_file', get_transforms, 'warp152.input_image')
full_process.connect(make_rcfe, 'rcfe.output_image', get_transforms, 'coreg_to_template_space.input_image')


