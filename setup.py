# setup.py
# Install script of ASyncRE modules
# Copyright (C) 2012 Emilio Gallicchio
# E-mail: emilio@biomaps.rutgers.edu
#
# This software is licensed under the terms of the GNU General Public License
# http://opensource.org/licenses/GPL-3.0
#
#    This program is free software: you can redistribute it and/or
#    modify it under the terms of the GNU General Public License
#    version 3 as published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
from distutils.core import setup
from pj_async_re import __version__ as VERSION

NAME = 'async_re'

MODULES = 'pj_async_re', 'date_async_re', 'impact_async_re', 'bedam_async_re', 'bedamtempt_async_re', 'amber_async_re', 'amberus_async_re', 'gibbs_sampling'

REQUIRES = 'bliss', 'configobj', 'numpy'

DESCRIPTION = 'Asynchronous Replica Exchange with Pilot-Job.'

AUTHOR = 'Emilio Gallicchio, Melissa Romanus, Brian Radak'

AUTHOR_EMAIL = 'emilio@biomaps.rutgers.edu'

setup(name=NAME,
      version=VERSION,
      description=DESCRIPTION,
      author=AUTHOR,
      author_email=AUTHOR_EMAIL,
      py_modules=MODULES,
      requires=REQUIRES
     )
