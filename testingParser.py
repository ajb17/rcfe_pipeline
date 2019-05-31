import nipype
from nipype.interfaces.io import JSONFileGrabber
# from nipype.interfaces.io import SelectFiles
from nipype import Function
from nipype import Node
from nipype import SelectFiles
from nipype import Workflow
# templates = {"epi": "/projects/abeetem/empty_full_bids/projects/testing_dir/sub-{subject_id}/ses-ALGA/func/sub-{subject_id}_ses-ALGA_task-rest_acq-{acq}_bold.nii.gz",
#              "T1": "/projects/abeetem/empty_full_bids/projects/testing_dir/sub-{subject_id}/ses-ALGA/anat/sub-{subject_id}_ses-ALGA_T1w.nii.gz"}
#
# dg = Node(SelectFiles(templates), "selectfiles")
#
# dg.iterables = ('subject_id', ['M10900840', 'M10900611'])
# dg.inputs.acq = '1400'
# dg.inputs.raise_on_empty = True

def print_path(path_string):
    print('\n\n\n')
    print(path_string)
    print('\n\n\n')
    return path_string

def split_path(path_string):
    print('\n\n splitting path \n\n')
    print(path_string.split())

print_path_node = Node(Function(function=print_path, output_names='output'), name='print_path')
print_path_node2 = Node(Function(function=print_path), name='print_path2')
split_path_node = Node(Function(function=split_path), name='split_path')
split_path_node2 = Node(Function(function=split_path), name='split_path2')

wf = Workflow("work")
# wf.connect(dg, 'T1', print_path_node, 'path_string')
# wf.connect(dg, 'epi', print_path_node2, 'path_string')
wf.connect(print_path_node, 'output', split_path_node, 'path_string')
# wf.run()




