import os
from os import path
import pandas as pd
from pandas import DataFrame as df
from nipype.interfaces.fsl import Merge
import math
import numpy as np
merge_order = [sub.rstrip().lstrip('_sub_') for sub in open('/projects/abeetem/results/goff_results/merge_order.txt')]

csv = pd.DataFrame.from_csv('/projects/abeetem/goff_data/goff_data_key.csv')
csv.drop(axis=1, index=np.nan, inplace=True)

merge_order_df = pd.DataFrame(merge_order)
csv = pd.merge(merge_order_df, csv, left_on=0, right_index=True, how='inner')

csv.Age = [int(n) for n in csv.Age]

csv.Gender.replace('F', 0, inplace=True)
csv.Gender.replace('M', 1, inplace=True)

csv['gmv'] = 1
csv['gm_age'] =  csv.Age - csv.Age.mean() #TODO: is it mean - age or vice versa?
csv['gm_sex'] =  csv.Gender - csv.Gender.mean()

csv.drop('Age', axis=1, inplace=True)
csv.drop("Gender", axis=1, inplace=True)
csv.drop(0, axis=1, inplace=True)

csv[['gmv', 'gm_age', 'gm_sex']].to_csv('/projects/abeetem/results/goff_results2/gm_info.csv', sep='\t', index=False)

# Create merge file
merged = Merge()
merge_paths = ["/projects/abeetem/results/goff_results2/epi_reg/full_process/_sub_{}/isoSmooth/rcfe_trans_smooth.nii".format(sub) for sub in merge_order]
merged.inputs.in_files = merge_paths
merged.inputs.dimension = 't'
merged.inputs.merged_file = '/projects/abeetem/results/goff_results2/merged.nii.gz'
merged.run()
