import argparse

ap = argparse.ArgumentParser()
ap.add_argument('-i', '--item', required=False, help='an item')
ap.add_argument('-l', '--list', nargs='*', required=False, help='a list of items')

args = vars(ap.parse_args())

item = args['item']
lis = args['list']

print '\n item: ' + item
print '\n list:'
print lis
