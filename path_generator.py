
import nipype
from os.path import abspath
import argparse
import os
from os import path

ap = argparse.ArgumentParser()
ap.add_argument('-t', '--template', required=True, help='The template you are fomatting to')
ap.add_argument('-p', '--param', required=True, help='The parameter you are substitutin into the template')
ap.add_argument('-f', '--file', required=True, help='The name of the output file')
args = vars(ap.parse_args())


temp = args['template']
param = open(args['param'], 'r').read().splitlines()
file = args['file']
# param = open(args['param'], 'r').readlines()

f = open(args['file'], 'w+')
for i in param:
    line = temp.format(i)
    if path.isfile(line.rstrip()):
        f.write(line)
        f.write('\n')

f.close()

