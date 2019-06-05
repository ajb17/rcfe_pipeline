from os import path
from datetime import datetime
from enum import Enum
Reg = Enum('Reg', 'epi t1')

draw_graphs = True
bias_correction = True
results_directory = path.expanduser('~') + '/rce_registration/' + str(datetime.now().isoformat())
registration = Reg.t1


