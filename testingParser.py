import argparse
from bids import BIDSLayout
from nipype.interfaces.io import BIDSDataGrabber
from nipype import Node, Function, Workflow

ap = argparse.ArgumentParser()
ap.add_argument('-sub', '--subject', required=False, help='You can specify a single subject to analyze here')
ap.add_argument('-temp', '--temp', required=True, help='The path to the template you are fitting your images to')
ap.add_argument('-d', '--directory', required=True, help='The directory that your subjects are all found in')
ap.add_argument('-t-ses', '--t1-session', required=False, help='The specific session you are looking for for t1 images')
ap.add_argument('-t-acq', '--t1-acquisition', required=False, help='The acquisition to look for in T1 images')
ap.add_argument('-t-task', '--t1-task', required=False, help='The task to look for in T1 images')
ap.add_argument('-f-ses', '--fmri-session', required=False, help='The session to look for in the fmri time series')
ap.add_argument('-f-acq', '--fmri-acquisition', required=False, help='The acquisition for fmri time series')
ap.add_argument('-f-task', '--fmri-task', required=False, help='The task to look for in fmri time series')

ap.add_argument('-ses', '--session', required=False, help='The session to look for in both T1 and fmri files')
ap.add_argument('-acq', '--acquisition', required=False, help='The acquisition to look for in both T1 and fmri files')
ap.add_argument('-task', '--task', required=False, help='The task to look for in both T1 and fmri files')


args = vars(ap.parse_args())


time_series_params = {"datatype": "func", "extensions": ["nii", ".nii.gz"]}
struct_params = {"datatype": "anat", "suffix": "T1w", "extensions": ["nii", ".nii.gz"]}


if args['task'] is not None:
    struct_params['task'] = args['task']
    time_series_params['task'] = args['task']

else:
    if args['fmri_task'] is not None:
        time_series_params['task'] = args['fmri_task']

    if args['t1_task'] is not None:
        struct_params['task'] = args['t1_task']

if args['acquisition'] is not None:
    struct_params['acquisition'] = args['acquisition']
    time_series_params['acquisition'] = args['acquisition']
else:
    if args['t1_acquisition'] is not None:
        struct_params['acquisition'] = args['t1_acquisition']
    if args['fmri_acquisition'] is not None:
        time_series_params['acquisition'] = args['fmri_acquisition']
if args['session'] is not None:
    struct_params['session'] = args['session']
    time_series_params['session'] = args['session']
else:
    if args['t1_session'] is not None:
        struct_params['session'] = args["t1_session"]
    if args['fmri_session'] is not None:
        time_series_params['session'] = args['fmri_session']


query = { 'time_series' : time_series_params, 'struct' : struct_params}

layout = BIDSLayout(args['directory'])

#TODO: eliminate search paths before files are created and resoruces are wasted



file_grabber = Node(BIDSDataGrabber(), name="grabber")
file_grabber.inputs.base_dir = args['directory']
file_grabber.inputs.output_query = query


if args['subject'] is not None:
   # file_grabber.iterables = ('subject', layout.get_subjects())#file_grabber.inputs.subject = 'M10999905'#args['subject']
    file_grabber.iterables = ('subject', [args['subject']])
    #file_grabber.inputs.subject = args['subject']
else:
    file_grabber.iterables = ('subject', layout.get_subjects())
file_grabber.inputs.raise_on_empty = False



def print_file(struct, ts):
    print('struct: {}'.format(struct))
    print('time series: {}'.format(ts))
print_file_node = Node(Function(function=print_file), name='print_file')
# print_file_node.inputs.raise_on_empty = False
# print_file_node.inputs.ignore_exception = True

pf = Workflow(name='workflow')
pf.connect(file_grabber, 'struct', print_file_node, 'struct')
pf.connect(file_grabber, 'time_series', print_file_node, 'ts')

pf.run('MultiProc', plugin_args={'n_procs':20})

# try:
#     pf.run('MultiProc', plugin_args={'n_procs':20})
# except (IOError, RuntimeError):
#     print("got the error")


