#!/usr/bin/env python
"""Setup for psremoteplay."""

from setuptools import find_packages, setup

version = {}
with open("./psremoteplay/__version__.py") as f:
    exec(f.read(), version)

MIN_PY_VERSION = '.'.join(map(str, version['REQUIRED_PYTHON_VER']))

REQUIRES = list(open('requirements.txt'))

CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Environment :: Console :: Curses',
    'Framework :: AsyncIO',
    'License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)',
    'Natural Language :: English',
    'Operating System :: OS Independent',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Topic :: Games/Entertainment',
    'Topic :: Home Automation',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: System :: Hardware',
]

with open('README.rst') as f:
    readme = f.read()

setup(name='psremoteplay',
      version=version['__version__'],
      description='PS5 psremoteplay Python Library',
      long_description=readme,
      long_description_content_type='text/markdown',
      author='vbbaccin',
      author_email='vitor.baccin@gmail.com',
      packages=find_packages(exclude=['tests']),
      url='https://github.com/vbbaccin/homeassistant/tree/main/components/psremoteplay',
      license='LGPLv3+',
      classifiers=CLASSIFIERS,
      keywords='playstation sony ps4 ps5 remote play remoteplay',
      install_requires=REQUIRES,
      python_requires='>={}'.format(MIN_PY_VERSION),
      test_suite='tests',
      include_package_data=True,
      entry_points={"console_scripts": ["psremoteplay = psremoteplay.__main__:cli"]}
      )
