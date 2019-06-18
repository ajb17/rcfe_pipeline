from os import path
from datetime import datetime
from enum import Enum
Reg = Enum('Reg', 'epi t1')

# draw_graphs = True
# bias_correction = True
# results_directory = path.expanduser('~') + '/rce_registration/' + str(datetime.now().isoformat())
# registration = Reg.t1

class config_class:
    def __init__(self):
        self.draw_graphs = True
        self.bias_correction = True
        self.results_directory = path.expanduser('~') + '/rce_registration/' + str(datetime.now().isoformat())
        self.registration = Reg.t1

config_object = config_class()

def set_draw_graphs(bool):
    # draw_graphs = bool
    print('\n\nbool\n\n')
    print(bool)
    print(type(bool))

    if bool == 0:
        # draw_graphs = False
        config_object.draw_graphs = False
    elif bool == 1:
        # draw_graphs = True
        config_object.draw_graphs = True
        print('setting true for draw_graphs')
    else:
        Exception("Please provide either an integer value of either 1 or 0. 1 to write out graphs. 0 to not write out graphs.")

def set_bias_correction(bool):
    bias_correction = bool

def set_results_directory(dir):
    results_directory = dir

def set_registraion(reg):
    # type: (Reg) -> Void
    registration = reg.name

def print_configuration():
    print('draw_graphs: ' + str(draw_graphs))
    print('bias_correction : ' + str(bias_correction))
    print('results_directory :' + results_directory)
    print('registration : ' + registration.name)

def configure():
    pass

def reset_defaults():
    draw_graphs = True
    bias_correction = True
    results_directory = path.expanduser('~') + '/rce_registration/' + str(datetime.now().isoformat())
    registration = Reg.t1

