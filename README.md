[![Build Status](https://travis-ci.org/biorack/omaat.png?branch=master)](https://travis-ci.org/biorack/omaat)

# OMAAT: OpenMSI Arrayed Analysis Tool

OpenMSI Arrayed Analysis Toolkit (OMAAT) is a new software package to analyze spatially defined samples in mass spectrometry imaging (MSI). Previously, researchers would either go through the data manually or rely on expert computer algorithms for large-scale region-of-interest based analysis. By using a Jupyter notebook, OMAAT becomes easily accessible to anyone without programming experience and makes performing peak finding and peak integration and in spatially defined samples in MSI datasets straightforward. In combination with OpenMSI, an powerful platform for storing, sharing and analyzing spatially defined MSI data is created and promotes the use of MSI for analyzing large arrayed sample sets. This new capability will greatly enable the use of laser-desorption ionization mass spectrometry imaging as a modality for high throughput biomolecular analysis. 

## Capabilties

* File selection
* Ion selection
* mask placement
* automatic marker position optimization
* visual representation
* data export


## Installation and Requirements

OMAAT is written as a Python module and primarity tested using the Anaconda Python distribution.  To exactly reproduce our test environment, see the distribution and packages [here](.travis.yml) and [here](setup.py).

Anaconda comes bundled with many python packages useful for data analysis.  If you already have Anaconda, make sure your packages are up to date.  OMAAT requires Jupyter version 4.1+ and python version 2.7+ or 3.2+. We recommend using the Anaconda distribution of python available here: https://www.continuum.io/downloads.

In addition to the base anaconda installation, you will need to install the python package, “future”.  With anaconda this is done using the conda package manager.

```
conda install future
```

The widgets in this notebook require the widgetsnbextension package.  This can be installed via:

```
conda install widgetsnbextension
jupyter nbextension enable --py --sys-prefix widgetsnbextension
```

OMAAT code can be obtained from the command line by:

```
git clone https://github.com/biorack/OpenMSI_Arrayed_Analysis_Tools.git
```
or by downloading and uncompressing the zip file of the repo here: https://github.com/biorack/OpenMSI_Arrayed_Analysis_Tools/archive/master.zip

To launch the notebook from a terminal, change to the OMAAT code directory.  And type
```
jupyter notebook
```
Or launch the notebook using the graphical Launcher tool from anaconda.

Python packages are constantly being updated.  Please contact us by placing a ticket here in github if you have any trouble using or installing omaat.

## Testing

Testing is performed using Travis-CI.  To reproduce a similar python environment to our [test](.travis.yml) from the omaat directory use:

```
>conda create -n omaat_python3 python=3.5 pytest pip numpy scipy jupyter matplotlib pandas
# or
>conda create -n omaat_python2 python=2.7 future pytest pip numpy scipy jupyter matplotlib pandas

>source activate omaat_python3
# or
>source activate omaat_python2

>python setup.py install
>pytest test/test_all.py
```

## Publications

*[Markus de Raad, Tristan de Rond, Oliver Rübe, Jay D. Keasling, Trent R. Northen, and Benjamin P. Bowen, "OpenMSI Arrayed Analysis Toolkit: Analyzing Spatially Defined Samples Using Mass Spectrometry Imaging" Anal. Chem., 2017, 89 (11), pp 5818–5823](http://pubs.acs.org/doi/abs/10.1021/acs.analchem.6b05004)
DOI: 10.1021/acs.analchem.6b05004

The data format for storage of MSI data is described in the following publication:

*Oliver Rübel, Annette Greiner, Shreyas Cholia, Katherine Louie, E. Wes Bethel, Trent R. Northen, and Benjamin P. Bowen, "OpenMSI: A High-Performance Web-Based Platform for Mass Spectrometry Imaging" Analytical Chemistry 2013 85 (21), 10354-10361, DOI: 10.1021/ac402540a. [[BibTeX]](https://openmsi.nersc.gov/site_media/openmsi/images/publications/openmsi_acs_2013.bib)[[Online at ACS]](http://pubs.acs.org/doi/abs/10.1021/ac402540a)*


## Licence

See [license.txt](license.txt)

## Copyright Notice

See [copyright.txt](copyright.txt)

