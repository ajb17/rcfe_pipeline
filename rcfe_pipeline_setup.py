# Author: Anthony Beetem
from nipype import Workflow, Node, Function
from nipype.interfaces.fsl import MCFLIRT, BET, FLIRT
from nipype.interfaces.fsl.maths import MeanImage, IsotropicSmooth
from nipype.interfaces.utility import Merge
from nipype.interfaces.afni import SkullStrip
from nipype.interfaces.ants import legacy, ApplyTransforms, N4BiasFieldCorrection
import nipype.interfaces.io as nio
from datetime import datetime
from os import path
from enum import Enum
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
Reg = Enum('Reg', 'epi t1')
config = {
    'bias_correction':True,
    'graphs':True,
    'registration':Reg.t1,
    'results_directory':path.expanduser('~') + '/rcfe_registration/' + str(datetime.now().isoformat()) + '/registration'

}

accept_input = Workflow(name='take_input')

def handle_input_files(time_series=[None], struct=[None]):
    """
    hanldes files input into the datagrabber nodes. Will return the files, unless they are wrapped in a list
    :param time_series:
    :param struct:
    :return:
    """
    if type(time_series) is not list:
        func = time_series
    else:
        func = time_series[0]
    if type(struct) is not list:
        anat = struct
    else:
        anat = struct[0]
    return func, anat

input_handler_node = Node(Function(function=handle_input_files, output_names=['time_series', 'struct']), name='input_handler')

def compute_rcFe(input_image, mask_image, invert_sign=True):
    import nibabel as nib
    import numpy as np
    from scipy import stats
    from os import path
    '''
    Just in case you want to return just the image (e.g. rendering or
    further processing).
    Author: Stan Colcombe
    '''
    in_image = nib.load(input_image).get_data()
    m_image = nib.load(mask_image).get_data()
    out_image = np.zeros(in_image.shape)
    idx = np.where(m_image)
    if (invert_sign):
        out_image[idx] = stats.zscore(in_image[idx]) * -1.0
    else:
        out_image[idx] = stats.zscore(in_image[idx])
        print("Note: NOT inverting z-scores.")
    img = nib.Nifti1Image(out_image, nib.load(input_image).affine)
    img.to_filename("rcfe.nii")

    return path.abspath("rcfe.nii")

# Motion correction on fmri time series
mcflirt_node = Node(MCFLIRT(mean_vol=True, output_type='NIFTI'), name="mcflirt")
# mcflirt_node = Node(MCFLIRT(mean_vol=True, output_type='NIFTI'), iterables=['in_file'], name="mcflirt")

# Compute mean(fslmaths) of the fmri time series
mean_fmri_node = Node(MeanImage(output_type='NIFTI'), name="meanimage")

# Skull Strip the fmri time series
bet_fmri_node = Node(BET(output_type='NIFTI', mask=True), name="bet_fmri")

# Bias Correct the fmri time series
bias_correction_node = Node(N4BiasFieldCorrection(), name='bias_correction')

# Returns the relative concentration of brain iron
rcfe_node = Node(Function(input_names=['input_image', 'mask_image'], output_names=['output_image'], function=compute_rcFe),
                 name="rcfe")



# coregister (skullstripped) mean of the fmri time series to the skull stripped T1 structural
flirt_node = Node(FLIRT(dof=6), name="flirt", cost='mutualinfo')  #TODO: do i have to specify out_matrix_file???

# skullstrip the T1 structural image
skullstrip_structural_node = Node(SkullStrip(outputtype='NIFTI'), name='skullstrip')

# coreg_to_struct_space = Node(FLIRT(apply_xfm=True, reference=struct_image, interp="sinc"), name="coreg")
coreg_to_struct_space_node = Node(FLIRT(apply_xfm=True, interp="sinc", cost='mutualinfo'), name="coreg_to_struct_space")


# Warp whole head T1 Structural Image to MNI 152 template
warp_to_152_node = Node(legacy.GenWarpFields(similarity_metric="CC"), name="warp152")

# coreg_to_template_space_node = Node(ApplyTransforms(reference_image=template, interpolation='BSpline'), name="coreg_to_template_space")
coreg_to_template_space_node = Node(ApplyTransforms(interpolation='BSpline'), name="coreg_to_template_space")

merge_transforms_node = Node(Merge(2), iterfield=['in2'], name="merge")

# Spatial smoothing
iso_smooth_node = Node(IsotropicSmooth(fwhm=4, output_type="NIFTI"), name='isoSmooth')

#TODO: Use the data sink node in the pipeline
data_sink_node = Node(nio.DataSink(base_directory="results_dir", container='warp152_output', infields=['tt']),
                      name='dataSink')


def set_template_image(template_image):
    """
    Sets the template image used to register the T1 or epi images to in the coregistration nodes.
    :param template_image: The path of the template image
    :return:
    """
    warp_to_152_node.inputs.reference_image = template_image
    coreg_to_template_space_node.inputs.reference_image = template_image

make_rcfe = Workflow(name='make_rcfe')
def setup_make_rcfe(bias_correction=config['bias_correction']):
    """
    Sets up the workflow that creates the rcfe image from an epi image
    :param bias_correction: Boolean. Whether you want the image to be bias corrected or not
    """
    make_rcfe.connect(mcflirt_node, 'out_file', mean_fmri_node, 'in_file')
    make_rcfe.connect(mean_fmri_node, 'out_file', bet_fmri_node, 'in_file')
    make_rcfe.connect(bet_fmri_node, 'mask_file', rcfe_node, 'mask_image')


    if bias_correction:
        make_rcfe.connect(bet_fmri_node, 'mask_file', bias_correction_node, 'mask_image')
        make_rcfe.connect(bet_fmri_node, 'out_file', bias_correction_node, 'input_image')
        make_rcfe.connect(bias_correction_node, 'output_image', rcfe_node, 'input_image')
    else:
        make_rcfe.connect(mean_fmri_node, 'out_file', rcfe_node, 'input_image') #TODO: uncomment this, and disconect N4bias from rcfe node later


get_transforms = Workflow(name="get_transforms")
def setup_get_transforms():
    """
    Sets up the workflow that gets the trasnformation matrices and affine matrices from the registration steps
    :return:
    """
    get_transforms.connect([(warp_to_152_node, merge_transforms_node, [('affine_transformation', 'in2'), ('warp_field', 'in1')])])
    get_transforms.connect(merge_transforms_node, 'out', coreg_to_template_space_node, 'transforms')


t1_wf = Workflow(name='t1')
def setup_t1_workflow():
    """
    Sets up the workflow that deals specifically with the pipeline that includes the transformation to structural space intermediate step
    :return:
    """
    t1_wf.connect(skullstrip_structural_node, 'out_file', flirt_node, 'reference')
    t1_wf.connect(flirt_node, 'out_matrix_file', coreg_to_struct_space_node, 'in_matrix_file')


accept_input.add_nodes([input_handler_node])

full_process = Workflow(name='full_process')

def setup_full_process(results_directory=config['results_directory'], bias_correction=config['bias_correction'], reg=config['registration'], graphs=config['graphs']):

    full_process.connect(get_transforms, 'coreg_to_template_space.output_image', iso_smooth_node, 'in_file')
    full_process.base_dir = results_directory
    full_process.connect(accept_input, 'input_handler.time_series', make_rcfe, 'mcflirt.in_file')

    if reg.name == 't1':
        full_process.connect([
            (make_rcfe, t1_wf, [('bet_fmri.out_file', 'flirt.in_file')]),
            (make_rcfe, t1_wf, [('rcfe.output_image', 'coreg_to_struct_space.in_file')]),
            (accept_input, get_transforms, [('input_handler.struct', 'warp152.input_image')]),
            (accept_input, t1_wf, [('input_handler.struct', 'skullstrip.in_file')]),
            (accept_input,t1_wf, [('input_handler.struct', 'coreg_to_struct_space.reference')]),
            (t1_wf, get_transforms, [('coreg_to_struct_space.out_file', 'coreg_to_template_space.input_image')])
        ])
    else:
        if bias_correction:
            full_process.connect(make_rcfe, 'bias_correction.output_image', get_transforms, 'warp152.input_image')
        else:
            full_process.connect(make_rcfe, 'bet_fmri.out_file', get_transforms, 'warp152.input_image')
        full_process.connect(make_rcfe, 'rcfe.output_image', get_transforms, 'coreg_to_template_space.input_image')

    if graphs:
        graph_name = results_directory + '/graphs/'
        full_process.write_graph(graph2use='colored', dotfilename=graph_name + 'colored', format='svg')
        full_process.write_graph(graph2use='flat', dotfilename=graph_name + 'flat', format='svg')

def setup():
    """
    After adjusting all the options in the config dictionary, call this fucntion to build your pipeline before running it.
    """
    setup_make_rcfe(config['bias_correction'])
    setup_get_transforms()
    setup_t1_workflow()
    setup_full_process(config['results_directory'], config['bias_correction'], config['registration'], config['graphs'])