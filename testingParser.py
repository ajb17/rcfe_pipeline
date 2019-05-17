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

class command_builder():
    def __init__(self):
        self.command = 'python cpac_epi_reg.py'
    #TODO: we need to return the instance in every below method in order to chain the methods
    #TODO: there has t be a way to remove all of this duplication, theres so much
    #TODO: should we prevent repeated calling? or is it fine cause the interface doesnt allow it?
    #TODO: should we also have the option to return nothing if nothing is given? this would let us call all the methods at once with no consequence
    #TODO: if we use these methods as the document is filled out, we may need a way for the builder to delete repeated trials
    def addSourceDir(self, dir):
        self.command = '{} -d {}'.format(self.command, dir)
        return self
    def addMeanImage(self, mean):
        self.command = '{} -m {}'.format(self.command, mean)
        return self
    def addBiasMask(self, mask):
        self.command = '{} -b {}'.format(self.command, mask)
        return self
    def addTemplatePage(self, temps):
        self.command = '{} -dt {}'.format(self.command, temps)
        return self
    def addTemplateImage(self, temp):
        self.command = '{} -t {}'.format(self.command, temp)
        return self
    def addTemplateParams(self, params):
        self.command = '{} -t {}'.format(self.command, params)
        return self
    def addProcesses(self, processes):
        self.command = '{} -p {}'.format(self.command, processes)
        return self

    def checkCommand(self):
        raise Exception("    ")
    def getCommand(self):
        return self.command

