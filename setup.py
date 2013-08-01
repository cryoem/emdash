import os
import subprocess
from distutils.core import setup
from emdash import __version__

if __name__ == "__main__":
    setup(
        name='emdash',
        version=__version__,
        description='EMDash -- Client utilities for EMEN2',
        author='Ian Rees',
        author_email='ian.rees@bcm.edu',
        url='http://blake.grid.bcm.edu/emanwiki/EMEN2/',
        packages=[
            'emdash',
            'emdash.ui'
            ],
        scripts=['scripts/emen2client.py', 'scripts/emdash_microscopy.py', 'scripts/emdash_upload.py']
        )
