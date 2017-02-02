"""Setup script for omaat package.
"""
DISTNAME = 'omaat'
DESCRIPTION = 'OpenMSI Arrayed Analysis Tools'
LONG_DESCRIPTION = open('README.md', 'rb').read().decode('utf-8')
MAINTAINER = 'Ben Bowen'
MAINTAINER_EMAIL = 'bpbowen@lbl.gov'
URL = 'http://github.com/biorack/omaat'
LICENSE = 'MIT'
REQUIRES = ["numpy", "pandas", "scipy", "matplotlib","ipywidgets","ipython"]
# , "buitins", "posixpath",
#             "scipy", "matplotlib", "getpass", "requests", 
#             "ipython", "future", "ipywidgets"]


CLASSIFIERS = """\
Development Status :: 2 - Pre-Alpha
Intended Audience :: Developers
Intended Audience :: Science/Research
Operating System :: OS Independent
Programming Language :: Python
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3.4
Topic :: Scientific/Engineering
Topic :: Software Development
"""


#ADD Versioning
# with open('omaat/__init__.py') as fid:
#     for line in fid:
#         if line.startswith('__version__'):
#             version = line.strip().split()[-1][1:-1]
#             break
from setuptools import setup, find_packages


if __name__ == "__main__":

    setup(
        name=DISTNAME,
        # version=version,
        maintainer=MAINTAINER,
        maintainer_email=MAINTAINER_EMAIL,
        url=URL,
        download_url=URL,
        # license=LICENSE,
        platforms=["Any"],
        description=DESCRIPTION,
        long_description=LONG_DESCRIPTION,
        classifiers=list(filter(None, CLASSIFIERS.split('\n'))),
        packages=find_packages(exclude=['doc']),
        include_package_data=True,
        zip_safe=False,  # the package can run out of an .egg file
        install_requires=REQUIRES,
        requires=REQUIRES,
     )