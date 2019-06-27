import argparse


ap = argparse.ArgumentParser()
ap.add_argument('-l', '--list', required=True, nargs='+')

args = vars(ap.parse_args())


for i in args['list']:
    print(i)


