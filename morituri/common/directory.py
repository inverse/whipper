# -*- Mode: Python; test-case-name: morituri.test.test_common_directory -*-
# vi:si:et:sw=4:sts=4:ts=4

# Morituri - for those about to RIP

# Copyright (C) 2013 Thomas Vander Stichele

# This file is part of morituri.
#
# morituri is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# morituri is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with morituri.  If not, see <http://www.gnu.org/licenses/>.

from os import getenv, makedirs
from os.path import join, expanduser, exists

def config_path():
    path = join(getenv('XDG_CONFIG_HOME') or join(expanduser('~'), u'.config'),
                u'whipper')
    if not exists(path):
        makedirs(path)
    return join(path, u'whipper.conf')

def cache_path(name=None):
    path = join(getenv('XDG_CACHE_HOME') or join(expanduser('~'), u'.cache'),
                u'whipper')
    if name:
        path = join(path, name)
    if not exists(path):
        makedirs(path)
    return path

def data_path(name=None):
    path = join(getenv('XDG_DATA_HOME')
                or join(expanduser('~'), u'.local/share'),
                u'whipper')
    if name:
        path = join(path, name)
    if not exists(path):
        makedirs(path)
    return path
