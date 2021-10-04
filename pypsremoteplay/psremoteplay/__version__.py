# -*- coding: utf-8 -*-
"""Constants for psremoteplay."""
MAJOR_VERSION = 1
MINOR_VERSION = 3
PATCH_VERSION = 1
REQUIRED_PYTHON_VER = (3, 6, 0)

__short_version__ = '{}.{}'.format(MAJOR_VERSION, MINOR_VERSION)
__version__ = '{}.{}'.format(__short_version__, PATCH_VERSION)

if __name__ == "__main__":
    print(__version__)
