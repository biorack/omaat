# import omaat_lib as omaat


import posixpath as path
import numpy as np
from scipy import interpolate
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import getpass
import json
import requests
import IPython.display
import ast
# import abc
import sys
import pandas as pd
import datetime
import time
import pickle
# import inspect
# from future.utils import with_metaclass

try:
    import ipywidgets
except ImportError:
    import IPython.html.widgets as ipywidgets

def test_simplest_test():
	pass

# def test_fileselector():
#     if "openMSIsession" not in locals():
#         openMSIsession=omaat.OpenMSIsession()
#         openMSIsession.imageLoader_with_dialogs() #once loaded the image will be stored in the "img" variable