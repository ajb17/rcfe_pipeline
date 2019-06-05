import rcfe_registration_config as config
from nipype import Node
from nipype import DataGrabber
#Optional: set custom output directory
config.results_directory = '/projects/abeetem/results/rcfe_piepline_custom_input_test'

# Step 1: Create your data grabbing node, and set up its inputs
data_grabber_node = Node(DataGrabber(base_directory='/projects/abeetem/goff_data', sort_filelist=True, raise_on_empty=False, outfields=['time_series', 'struct'], infields=['sub']), name='data_grabber')
data_grabber_node.inputs.template = '*'
data_grabber_node.inputs.raise_on_empty = False
data_grabber_node.inputs.drop_blank_outputs = True
data_grabber_node.inputs.field_template = dict(time_series='/projects/stan/goff/recon/TYY-%s/ep2d_bold_TR_300_REST.nii', struct='/projects/stan/goff/recond/TYY-%s/t1_to_mni.nii.gz')

subs = [i[0:i.find(',')] for i in open('/projects/abeetem/goff_data/goff_data_key.csv', 'r')][2:7] # = ['Ndyx501a', 'Ndyx501c', 'Ndyx502a', 'Ndyx503a', 'Ndyx505a']
data_grabber_node.inputs.template_args['struct'] = [['sub']]
data_grabber_node.inputs.template_args['time_series'] = [['sub']]
data_grabber_node.iterables = [('sub', subs)]

#TODO: consider just making a function to call to swithc them
#Optional: if you are using the epi template registraion, (and skipping the t1 registration, set the optioni)
config.registration = config.Reg.epi

#Step 2: Import the pipeline steup file only after setting all the configurations in the pieplines config file
import rcfe_registration_node_setup
from rcfe_registration_node_setup import full_process
from rcfe_registration_node_setup import input_handler_node
from rcfe_registration_node_setup import accept_input

#Step 3: connect your custom data grabbing nod to the input handling node from the setup file
accept_input.connect([(data_grabber_node, input_handler_node, [('time_series', 'time_series'), ('struct', 'struct')])])

#Step 4: set the template image that your images are being registered to
rcfe_registration_node_setup.set_template_image('/projects/abeetem/goff_data/epi_template.nii.gz')

#Steo 5: Run the process
full_process.run('MultiProc', plugin_args={'n_procs': 10})
