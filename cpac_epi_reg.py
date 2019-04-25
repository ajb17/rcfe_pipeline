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
#import itertools

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
args = vars(ap.parse_args())


# TODO: What is the input type for images?
# we should end up wiht a list of image paths at least

#TODO: split up the mean image and the derivatice image findin into tow funcitons instead
def path_generator(sub, ses=None):
    import os
    from os.path import abspath
    # mean_image = None
    # if mean_image:
    mean_image_string =  '/projects/cgutierrez/rockland_sample_cpac/All_Outputs/{}_{}/mean_functional/_scan_rest_acq-1400/sub-{}_ses-{}_task-rest_acq-1400_bold_calc_resample_volreg_calc_tstat.nii.gz'.format(sub, ses, sub, ses)
    mean_image = abspath(mean_image_string)
       # mean_image = abspath("/projects/cgutierrez/rockland_sample_cpac/All_Outputs/{}/mean_functional/_scan_rest_acq/1400/sub-{}_ses-{}_task-rest_acq1400_bold_calc_resample_volreg_calc_tstat.nii.gz".format(sub, sub, ses))
        #print mean_image
    reho = abspath("/projects/cgutierrez/rockland_sample_cpac/All_Outputs/{}_{}/raw_reho_map/_scan_rest_acq-1400/_compcor_ncomponents_5_selector_pc10.linear1.wm0.global1.motion1.quadratic1.gm0.compcor1.csf0/_bandpass_freqs_0.01.10.0/ReHo.nii.gz").format(sub, ses)
    res_filt = abspath("/projects/cgutierrez/rockland_sample_cpac/All_Outputs/{}_{}/alff_img/_scan_rest_acq-1400/_compcor_ncomponents_5_selector_pc10.linear1.wm0.global1.motion1.quadratic1.gm0.compcor1.csf0/_hp_0.01/_lp_0.1/residual_filtered_3dT.nii.gz").format(sub, ses)
    # return reho if os.path.isfile(reho) else res_filt if os.path.isfile(res_filt) else "No file found"
    # print(res_filt)
    # print(os.path.isfile(res_filt))
    return mean_image if os.path.isfile(mean_image) else None, res_filt if os.path.isfile(res_filt) else None, reho if os.path.isfile(reho) else None

def mean_path(sub, ses=None):
    mean_image = abspath(
        '/projects/cgutierrez/rockland_sample_cpac/All_Outputs/{}_{}/mean_functional/_scan_rest_acq-1400/sub-{}_ses-{}_task-rest_acq-1400_bold_calc_resample_volreg_calc_tstat.nii.gz'.format(
            sub, ses, sub, ses))
    return mean_image


def reho_path(sub, ses):
    return abspath("/projects/cgutierrez/rockland_sample_cpac/All_Outputs/{}_{}/raw_reho_map/_scan_rest_acq-1400/_compcor_ncomponents_5_selector_pc10.linear1.wm0.global1.motion1.quadratic1.gm0.compcor1.csf0/_bandpass_freqs_0.01.10.0/ReHo.nii.gz".format(sub, ses))
def res_filt_path(sub, ses):
    return abspath("/projects/cgutierrez/rockland_sample_cpac/All_Outputs/{}_{}/alff_img/_scan_rest_acq-1400/_compcor_ncomponents_5_selector_pc10.linear1.wm0.global1.motion1.quadratic1.gm0.compcor1.csf0/_hp_0.01/_lp_0.1/residual_filtered_3dT.nii.gz".format(sub[1:], ses))
    #TODO: should i thorw an error if no file is found, or is this an expected thing?


if args['starter'] is not None:
    start_images = [args['starter']]
elif args['sub_list'] is not None and args['ses_list'] is not None:
    start_images = [path_generator(sub, ses) for sub in args['sub_list'] for ses in args['ses_list']]


template = abspath(args['template'])
if args['images'] is not None:
    image_paths = args['images']
elif args['image_path_source'] is not None:

    image_paths = args['image_path_source']
elif args['sub_list'] is not None and args['ses_list'] is not None:
    image_paths_lists = [path_generator(sub, ses) for sub in args['sub_list'] for ses in args['ses_list']]
    image_paths = [path for list in image_paths_lists for path in list]
else:
    raise Exception("Should specify images as either a list of image paths, or an iterable source of image paths, such as a textfile, or specify a list of subjects and sessions and directory to search through")


if args['sub_list'] is not None:
    if args['ses_list'] is None:
        raise Exception('Must specify ses_list if sub_list is specified')
    sub_list = args['sub_list']
    ses_list = args['ses_list']
sub_list = [sub.rstrip('\n') for sub in open(args['sub_list'], 'r')]
ses_list = [ses.rstrip('\n') for ses in open(args['ses_list'], 'r')]
sub_ses_dict = None
if args['sub_list'] is not None and args['ses_list'] is not None:
    #sub_ses_dict = {"{}_{}".format(args[sub], args[ses]):path_generator(sub, ses) for sub in args['sub_list'] for ses in args['ses_list']}
    sub_ses_dict = {"{}_{}".format(sub.rstrip('\n'), ses.rstrip('\n')): path_generator(sub.rstrip('\n'), ses.rstrip('\n')) for sub in open(args['sub_list'], 'r') for ses in open(args['ses_list'], 'r')}
    #sub_ses_dict = {"{}_{}".format(sub.rstrip('\n'), ses.rstrip('\n')): [reho_path(sub, ses)] + [res_filt_path(sub, ses)] for sub in args['sub_list'] for ses in args['ses_list']}
print(sub_ses_dict)

input_node = Node(Function(output_names=['mean', 'res', 'reho'], function=path_generator), iterables=[('sub', sub_list), ('ses', ses_list)], name='input_node')

def print_inputs(mean, res, reho):
    print('hello', mean, res, reho)
print_node = Node(Function(function=print_inputs), name='print_inputs')
#
# testflow = Workflow(name='test', base_dir='/projects/abeetem/results/cpac_epi_reg')
# testflow.connect([(input_node, print_node, [('mean', 'mean'), ('res','res'),('reho', 'reho')])])
# # testflow.connect([(input_node, print_node, [('outputs.mean', 'inputs.mean'), ('outputs.res','inputs.res'),('outputs.reho', 'inputs.reho')])])
# testflow.run()


generate_transforms_node = Node(legacy.GenWarpFields(reference_image=template), name='generate_transforms')

merge_transforms_node = Node(Merge(2), iterfield='in2', name='merge_transforms')


#apply_transforms_node = Node(ApplyTransforms(reference_image=template, interpolation='BSpline'), iterables=, name='apply_transform')

merge_input_files_node = Node(Merge(2), iterfield='in2', name='merge_input_files')
map_apply_node = MapNode(interface=ApplyTransforms(reference_image=template, interpolation='BSpline'), iterfield=['input_image'], name='map_apply_node')

transform_images = Workflow(name='cpac_epi_reg',base_dir=args['results_dir'])# base_dir='/projects/abeetem/results/cpac_epi_reg')

transform_images.connect([(input_node, generate_transforms_node, [('mean', 'input_image')])])
#TODO: the input images are selected by the input node, but the

transform_images.connect([(input_node, merge_input_files_node, [('reho', 'in1'), ('res', 'in2')])])
# transform_images.connect([(merge_input_files_node, apply_transforms_node, [('out', 'input_image')])])
transform_images.connect([(merge_input_files_node, map_apply_node, [('out', 'input_image')])])


# transform_images.connect([(input_node, apply_transforms_node, [('reho', 'input_image')])]) #TODO: not just reho later

transform_images.connect([(generate_transforms_node, merge_transforms_node, [('affine_transformation', 'in2'), ('warp_field', 'in1')])])
#transform_images.connect(merge_transforms_node, 'out', apply_transforms_node, 'transforms')
transform_images.connect(merge_transforms_node, 'out', map_apply_node, 'transforms')

transform_images.write_graph(graph2use='orig', dotfilename='./cpac_epi_reg_orig', format='svg')
transform_images.write_graph(graph2use='colored', dotfilename='./cpac_epi_reg_colored', format='svg')
transform_images.write_graph(graph2use='exec', dotfilename='./cpac_epi_reg_exec', format='svg')

transform_images.run('MultiProc', plugin_args={'n_procs':30})

"""
Input mean image: 
/projects/cgutierrez/rockland_sample_cpac/All_Outputs/M10936246_DS2/mean_functional/_scan_rest_acq/1400/sub-M10936246_ses-DS2_task-rest_acq1400_bold_calc_resample_volreg_calc_tstat.nii.gz

apply transforms to these:
/projects/cgutierrez/rockland_sample_cpac/All_Outputs/M10936246_DS2/alff_img/_scan_rest_acq-1400/_compcor_ncomponents_5_selector_pc10.linear1.wm0.global1.motion1.quadratic1.gm0.compcor1.csf0/_hp_0.01/_lp_0.1/residual_filtered_3dT.nii.gz

/projects/cgutierrez/rockland_sample_cpac/All_Outputs/10936246_DS2/raw_reho_map/_scan_rest_acq-1400/_compcor_ncomponents_5_selector_pc10.linear1.wm0.global1.motion1.quadratic1.gm0.compcor1.csf0/_bandpass_freqs_0.01.10.0/ReHo.nii.gz
"""

'''


#generate_transforms_node = Node(legacy.GenWarpFields(input_image=start_image, reference_image=template), name='generate_transforms')
generate_transforms_node = Node(legacy.GenWarpFieldsi(reference_image=template), iterables=('input_image', start_images), name='generate_transforms')

merge_transforms_node = Node(Merge(2), iterfield='in2', name='merge_transforms')

apply_transforms_node = Node(ApplyTransforms(reference_image=template, interpolation='BSpline'), iterables=('input_image', image_paths), name='apply_transform')


transform_images = Workflow(name='cpac_epi_reg',base_dir = args['results_dir']# base_dir='/projects/abeetem/results/cpac_epi_reg')
transform_images.connect([(generate_transforms_node, merge_transforms_node, [('affine_transformation', 'in2'), ('warp_field', 'in1')])])
transform_images.connect(merge_transforms_node, 'out', apply_transforms_node, 'transforms')

transform_images.write_graph(graph2use='orig', dotfilename='./test_orig', format='svg')
transform_images.write_graph(graph2use='colored', dotfilename='./test_colored', format='svg')
transform_images.run()

'''


















