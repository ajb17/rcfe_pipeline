from os.path import abspath
from nipype import Workflow, Node, MapNode
from nipype.interfaces.utility import Merge
from nipype.interfaces.ants import legacy, ApplyTransforms, N4BiasFieldCorrection
import argparse
import nipype.interfaces.io as nio
from nipype import DataGrabber


"""
This is a pipeline used to create a set of transforms, and then apply them to a batch of images you want to see
transformed in the same space.

The program requires at least three thing:
    1) An image that is initially being transformed into a template space (refered to here as a mean image)
    2) A template that the mean image is applied to
    3) Any images you want the resulting trasnforms to also be applied to 
    4) (Optional) a mask image used in N4 Bias correction


These requirnments can be met in two ways
    The first way is to supply a -m mean_image_path, a -t template_path,
    a -b bias_masking_path, and -i image1_path, image2_path, ...
    This is very straight forward and useful when you want to quickly check the resulting trasnformation on a set 
    of files you can grab very easily with somehting like shell globbing, or copy pasting
    
    The other method is more expansive, and lets you create path templates, that nipype will use to seek out files for you.
    This is great for very large amounts of files with several groupings of similar file paths.
    In the text file you will define a label for a groupd of images, then you will write out the path to one of the files,
    while wildcarding any parts of the path that may vary between other similar files, then you create, in order, labels of
    the parameters that will be filled into those templates
    for example an entry may look like so
    "/home/Desktop/sub-123_ses-5/ReHo.nii.gz"
    group name:          path template:                            parameter names:
    derivative_image_1, "/home/Desktop/sub-%s_ses-%s/ReHo.nii.gz", sub, ses
    
    to provide the values that will be substituted in for each paramter such as sub, you will
    need to provide a list values in the form of a text file
    
     

"""
#TODO: provide the option to put the text file link write into the template file itself

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


# This creates the templates and template arguments that are accepted by Nipype's data grabber
def parse_template_entry(entry):
    key = entry[:min(entry.find(' '), entry.find('='))]
    first_quote_index = entry.find('"')
    second_quote_index = entry.find('"', first_quote_index+1)
    template = entry[first_quote_index+1: second_quote_index]
    args = [arg for arg in entry[second_quote_index+1:].split(',') if arg is not '']
    return key, template, args

# This is where we build up the dictionaries of templates and arguments for the nipype data grabber
temps_dict = {}
temp_args_dict = {}
if args['derivatives'] is not None:
    for i in open(args['derivatives'], 'r'):
        if i is '' or i == '\n':
            continue
        key, temp, targs = parse_template_entry(i)
        temps_dict[key] = temp.rstrip("\n")
        temp_args_dict[unicode(key)] = [[arg.rstrip('\n').lstrip(' ') for arg in targs if arg is not '']]#TODO: I wrapped this in a list for a reason, probably to match something in nipype, but should see if i can remove it, it complicates a few things down the road
        #TODO: this would probably be a little more efficient to do it as we create the list if possible



    derivatives_names = temps_dict.keys()
    derivatives_names.remove('mean')
    if 'bias_mask' in derivatives_names:
        derivatives_names.remove('bias_mask')

    temp_args = args['template_arguments']
    # This formats the above list into a dictionary where we can much more easily associate keywords to their lists
    template_arguments = {temp_args[::2][i]: temp_args[1::2][i] for i in range(len(temp_args) / 2)} #TODO: is this dictionary comprehension too much?


    data_grabber_node = Node(DataGrabber(base_directory=args['directory'], sort_filelist=True, raise_on_empty=False, infields=template_arguments.keys(), outfields=[tmp for tmp in temps_dict]), name='data_grabber')
    data_grabber_node.inputs.template = '*'
    data_grabber_node.inputs.raise_on_empty = True
    data_grabber_node.inputs.drop_blank_outputs = True
    data_grabber_node.inputs.field_template = temps_dict
    data_grabber_node.inputs.template_args = temp_args_dict
    data_grabber_node.iterables = [ (  key,
                                       [thing.rstrip('\n') for thing in open(template_arguments[key], 'r')]
                                    )
                                    for key in template_arguments.keys()] #TODO: Is nested list comprehenion too much?
                                    #[('sub', sub_list), ('ses', ses_list)]

template = abspath(args['template'])
bias_correction_node = Node(N4BiasFieldCorrection(), name='bias_correction')
generate_transforms_node = Node(legacy.GenWarpFields(reference_image=template), name='generate_transforms')
merge_transforms_node = Node(Merge(2), iterfield='in2', name='merge_transforms')

if args['derivatives'] is not None:
    merge_input_files_node = Node(Merge(len(derivatives_names)), name='merge_input_files')

map_apply_node = MapNode(interface=ApplyTransforms(reference_image=template, interpolation='BSpline'), iterfield=['input_image'], name='map_apply_node')

transform_images = Workflow(name='cpac_epi_reg', base_dir=args['results_dir'])# base_dir='/projects/abeetem/results/cpac_epi_reg')

if args['derivatives'] is not None:
    #TODO: do reho, res, bias mask are all hardcoded here, but they shouldnt be
    if 'bias_mask' in temps_dict:
        transform_images.connect([(data_grabber_node, bias_correction_node, [('bias_mask', 'mask_image')])])
        transform_images.connect([(data_grabber_node, bias_correction_node, [('mean', 'input_image')])])
        transform_images.connect([(bias_correction_node, generate_transforms_node, [('output_image', 'input_image')])])
    else:
        #TODO: Should I print an indication that no bias mask was used? It didnt have much of an impact on the final results from what i could tell at least
        transform_images.connect([(data_grabber_node, generate_transforms_node, [('mean', 'input_image')])])
    #TODO: the input images are by the input node, but the

    transform_images.connect([(data_grabber_node, merge_input_files_node, [(derivatives_names[i], 'in' +str(i+1)) for i in range(len(derivatives_names))])])
    transform_images.connect([(merge_input_files_node, map_apply_node, [('out', 'input_image')])])
elif args['mean'] is not None and args['images'] is not None:
    if args['bias'] is not None:
        bias_correction_node.inputs.mask_image = args['bias']
        bias_correction_node.inputs.input_image = args['mean']
        transform_images.connect([(bias_correction_node, generate_transforms_node, [('output_image', 'input_image')])])
        map_apply_node.inputs.input_image = args['images']
    else:
        generate_transforms_node.inputs.input_image = args['mean']
        map_apply_node.inputs.input_image = args['images']

transform_images.connect([(generate_transforms_node, merge_transforms_node, [('affine_transformation', 'in2'), ('warp_field', 'in1')])])
transform_images.connect(merge_transforms_node, 'out', map_apply_node, 'transforms')

data_sink_node = Node(nio.DataSink(base_directory=args['results_dir'] + 'output'), name='data_sink')
transform_images.connect(generate_transforms_node, 'output_file', data_sink_node, 'output_file')
transform_images.connect(map_apply_node, 'output_image', data_sink_node, 'output_image')


if args['show_graphs']:
    transform_images.write_graph(graph2use='orig', dotfilename='./graphs/cpac_epi_reg_orig', format='svg')
    transform_images.write_graph(graph2use='colored', dotfilename='./graphs/cpac_epi_reg_colored', format='svg')
    transform_images.write_graph(graph2use='exec', dotfilename='./graphs/cpac_epi_reg_exec', format='svg')

transform_images.run('MultiProc', plugin_args={'n_procs':args['processes']})
# TODO: The mean image and the bias mask are hard coded values, that must be specified in a text file and they must be name 'mean' and 'bias_mask" exaclty.
#I need to adjust the rigidity of this, ideally wihtout writing every possible 'bias_mask' 'BiasMask' combination, and wihtout having to create even more text files
#to hold each no derivative template.

