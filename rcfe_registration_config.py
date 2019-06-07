from os import path
from datetime import datetime
from enum import Enum
Reg = Enum('Reg', 'epi t1')

draw_graphs = True
bias_correction = True
results_directory = path.expanduser('~') + '/rce_registration/' + str(datetime.now().isoformat())
registration = Reg.t1

def set_draw_graphs(bool):
    draw_graphs = bool

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
