#import cpac_epi_reg
#import tkinter as tk
from tkinter import *
fields = 'Source Directory', 'Mean Image', 'Template Image', 'Mask Image', 'Derivatives', 'Template Parameters', 'Processes'
import os
import subprocess
from functools import partial
import time

# from tkFileDialog import askopenfilename
# def callback():
#     name = askopenfilename()
#     print(name)
# errmsg = 'Error!'
# Button(text='File Open', command=callback).pack(fill=X)
# mainloop()


template_file_name = 'template_file_' +time.strftime('%Y%m%d-%H%M%S')+'.txt'
# template_file = open('template_file_' +time.strftime('%Y%m%d-%H%M%S')+'.txt', 'a')
loe = []
def read_loe():
    for i in loe:
        print(i.get())
template_page_entries = []
def write_template_file():
    template_file = open(template_file_name, 'a')
    template_file.seek(0)
    template_file.truncate()
    for i in template_page_entries:
        template_file.write(i.write()+"\n")
    template_file.close()

class command_builder():
    def __init__(self):
        self.command = 'echo python cpac_epi_reg.py'
        #TODO: Remove the echo command when ready to use
        self.source = ''
        self.mean = ''
        self.mask = ''
        self.tempPage = ''
        self.temp = ''
        self.tempParams = ''
        self.processesCount = ''

    #TODO: we need to return the instance in every below method in order to chain the methods
    #TODO: there has t be a way to remove all of this duplication, theres so much
    #TODO: should we prevent repeated calling? or is it fine cause the interface doesnt allow it?
    #TODO: should we also have the option to return nothing if nothing is given? this would let us call all the methods at once with no consequence
    #TODO: if we use these methods as the document is filled out, we may need a way for the builder to delete repeated trials
    def sourceDir(self, dir):
        if dir is None or dir is '':
            return self
        self.source = '-d {}'.format(dir)
        return self
    def meanImage(self, mean):
        if mean is None or mean is '':
            return self
        self.mean = '-m {}'.format(mean)
        return self
    def biasMask(self, mask):
        if mask is None or mask is '':
            return self
        self.mask = '-b {}'.format(mask)
        return self
    def templatePage(self, temps):
        if temps is None or temps is '':
            return self
        self.tempPage = '-dt {}'.format(temps)
        return self
    def templateImage(self, temp):
        if temp is None or temp is '':
            return self
        self.temp = '-t {}'.format(temp)
        return self
    def templateParams(self, params):
        if params is None or params is '':
            return self
        self.tempParams = '-ta {}'.format(params)
        return self
    def processes(self, processes):
        if processes is None or processes is '':
            return self
        self.processesCount = '-p {}'.format(processes)
        return self

    def checkCommand(self):
        raise Exception("    ")
    def getCommand(self):
        return '{} {} {} {} {} {} {} {}'.format(self.command, self.source, self.mean, self.mask, self.tempPage, self.temp, self.processesCount, self.tempParams)

class temp:
    def __init__(self, label=None, template=None, params=[]):
        self.label = label
        self.template = template
        self.params = params
    def write(self):
        full_line = "{}, {}".format(self.label.get(), self.template.get())
        for i in self.params:
            full_line += ', {}'.format(i.get())

        return full_line


def fetch(entries):
    for entry in entries:
        field = entry[0]
        text = entry[1].get()
        print('%s: "%s"' % (field, text))
form = {'mean':None, 'template':None, 'directory':None, }
def makeform(root, fields):
    entries = []
    for field in fields:
        row = Frame(root)
        lab = Label(row, width=15, text=field, anchor='w')
        ent = Entry(row)
        form[field] = ent
        if field is 'Derivatives':
            ent.insert(END, template_file_name)


        row.pack(side=TOP, fill=X, padx=5, pady=5)
        lab.pack(side=LEFT)
        ent.pack(side=RIGHT, expand=YES, fill=X)
        entries.append((field, ent))

        #TODO: should call expand derivatives twice and start one labeled mean image and the other bias mask

    return entries




def expand_derivatives(root, num):
    derivative = temp()
    derivative.params = []
    template_page_entries.append(derivative)
    row = Frame(root)
    params = Frame(row)
    ent = Entry(row)
    derivative.label = ent
    template = Entry(row)
    derivative.template = template

    def add_entry():
        e = Entry(params)
        e.pack(side=LEFT, expand=YES, fill=X)
        derivative.params.append(e)
        #TODO: These are probably going to be in reverse order when added
    row.pack(side=TOP, fill=X, padx=5, pady=5)
    params.pack(side=RIGHT, fill=X, padx=5, pady=5)
    add_params_button = Button(row, text='param', command=add_entry)
    add_params_button.pack(side=RIGHT, padx=5)
    template.pack(side=RIGHT, expand=YES, fill=X)
    ent.pack(side=RIGHT, expand=YES, fill=X)

def execute():
    write_template_file()
    #TODO: Leaave the option to provide a tempalte file instead of creating one
    #TODO: dont create one if they jsut provide images in place of the templates
    #TODO: leave the option to not write out the file if they provide one

    # subprocess.check_output(['python', 'cpac_epi_reg.py', '-m', ,'-t', , '-b', , '-dt', template_file_name, '-d', , '-ta', , '-p', ])
    command = command_builder()\
        .meanImage(form['Mean Image'].get())\
        .processes(form['Processes'].get())\
        .sourceDir(form['Source Directory'].get())\
        .biasMask(form['Mask Image'].get())\
        .templateImage(form['Template Image'].get())\
        .templatePage(form['Derivatives'].get())\
        .templateParams(form['Template Parameters'].get())\
        .getCommand()
    print(command)
    subprocess.check_output(command.split())
if __name__ == '__main__' or __name__:
    root = Tk()
    ents = makeform(root, fields)
    print(ents)
    root.bind(' m', (lambda event, e=ents: fetch(e)))
    b1 = Button(root, text='show', command=(lambda e=ents: fetch(e)))
    b1.pack(side=LEFT, padx=5, pady=5)
    b2 = Button(root, text='Quit', command=root.quit())
    b2.pack(side=LEFT, padx=5, pady=5)
    add_derivatives_command = partial(expand_derivatives, root, 5)
    add_derivatives_button = Button(root, text='Add Derivative', command=add_derivatives_command)
    add_derivatives_button.pack()
    derivative_label_row = Frame(root)
    lab = Label(derivative_label_row, width=15, text='label', anchor='w')

    temp_lab = Label(derivative_label_row, width=15, text='template:', anchor='w')
    derivative_label_row.pack()
    lab.pack(side=RIGHT)
    temp_lab.pack(side=RIGHT)

    # execute_button = Button(root, text='execute', command=write_template_file)
    execute_button = Button(root, text='execute', command=execute)
    execute_button.pack(side=LEFT, padx=5, pady=5)
    root.mainloop()


# root = tk.Tk()
# root.title('My GUI')
# label = tk.Label(root, text= "hello, world!")
# label.pack()
# root.mainloop()


