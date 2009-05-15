# -*- Mode: Python; test-case-name: morituri.test.test_image_toc -*-
# vi:si:et:sw=4:sts=4:ts=4

# Morituri - for those about to RIP

# Copyright (C) 2009 Thomas Vander Stichele

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

"""
Reading .toc files
"""

import os
import re

from morituri.common import common, log
from morituri.image import table

# shared
_CDTEXT_CANDIDATE_RE = re.compile(r'(?P<key>\w+) "(?P<value>.+)"')

# header
_CATALOG_RE = re.compile(r'^CATALOG "(?P<catalog>\d+)"$')

# records
_TRACK_RE = re.compile(r"""
    ^TRACK            # TRACK
    \s(?P<mode>.+)$   # mode (AUDIO, MODEx/2xxx, ...)
""", re.VERBOSE)

_ISRC_RE = re.compile(r'^ISRC "(?P<isrc>\w+)"$')

# a HTOA is marked in the cdrdao's TOC as SILENCE
_SILENCE_RE = re.compile(r"""
    ^SILENCE              # SILENCE
    \s(?P<length>.*)$     # pre-gap length
""", re.VERBOSE)


_FILE_RE = re.compile(r"""
    ^FILE                 # FILE
    \s+"(?P<name>.*)"     # 'file name' in quotes
    \s+(?P<start>.+)      # start offset
    \s(?P<length>.+)$     # stop offset
""", re.VERBOSE)

# FIXME: start can be 0
_START_RE = re.compile(r"""
    ^START                # START
    \s(?P<length>.*)$     # pre-gap length
""", re.VERBOSE)


_INDEX_RE = re.compile(r"""
    ^INDEX            # INDEX
    \s(?P<offset>.+)$ # start offset
""", re.VERBOSE)

class TocFile(object, log.Loggable):
    def __init__(self, path):
        self._path = path
        self._messages = []
        self.table = table.IndexTable()

    def parse(self):
        state = 'HEADER'
        currentFile = None
        currentTrack = None
        counter = 0
        trackNumber = 0
        indexNumber = 0
        currentOffset = 0 # running absolute offset of where each track starts
        currentLength = 0 # accrued during TRACK record parsing, current track
        pregapLength = 0 # length of the pre-gap, current track


        # the first track's INDEX 1 can only be gotten from the .toc
        # file once the first pregap is calculated; so we add INDEX 1
        # at the end of each parsed  TRACK record
        handle = open(self._path, 'r')

        for number, line in enumerate(handle.readlines()):
            line = line.rstrip()

            # look for CDTEXT stuff in either header or tracks
            m = _CDTEXT_CANDIDATE_RE.search(line)
            if m:
                key = m.group('key')
                value = m.group('value')
                if key in table.CDTEXT_FIELDS:
                    # FIXME: consider ISRC separate for now, but this
                    # is a limitation of our parser approach
                    if state == 'HEADER':
                        self.table.cdtext[key] = value
                        self.debug('Found disc CD-Text %s: %s', key, value)
                    elif state == 'TRACK':
                        if key != 'ISRC' or not currentTrack \
                            or currentTrack.isrc is not None:
                            self.debug('Found track CD-Text %s: %s', key, value)
                            currentTrack.cdtext[key] = value

            # look for header elements
            m = _CATALOG_RE.search(line)
            if m:
                self.table.catalog = m.group('catalog')
                self.debug("Found catalog number %s", self.table.catalog)

            # look for TRACK lines
            m = _TRACK_RE.search(line)
            if m:
                state = 'TRACK'

                # set index 1 of previous track if there was one, using
                # pregapLength if applicable
                if currentTrack:
                    currentTrack.index(1, path=currentFile.path,
                        relative=currentOffset + pregapLength, counter=counter)
                    self.debug('track %d, added index %r',
                        currentTrack.number, currentTrack.getIndex(1))

                trackNumber += 1
                currentOffset += currentLength
                currentLength = 0
                indexNumber = 1
                trackMode = m.group('mode')
                pregapLength = 0

                # FIXME: track mode
                currentTrack = table.ITTrack(trackNumber)
                self.table.tracks.append(currentTrack)
                continue

            # look for ISRC lines
            m = _ISRC_RE.search(line)
            if m:
                isrc = m.group('isrc')
                currentTrack.isrc = isrc
                self.debug('Found ISRC code %s', isrc)

            # look for SILENCE lines
            m = _SILENCE_RE.search(line)
            if m:
                if currentFile is not None:
                    self.debug('SILENCE after FILE, increasing counter')
                    counter += 1
                    currentFile = None
                length = m.group('length')
                currentLength += common.msfToFrames(length)

            # look for FILE lines
            m = _FILE_RE.search(line)
            if m:
                filePath = m.group('name')
                start = m.group('start')
                length = m.group('length')
                self.debug('FILE %s, start %r, length %r',
                    filePath, common.msfToFrames(start),
                    common.msfToFrames(length))
                if not currentFile or filePath != currentFile.path:
                    counter += 1
                    self.debug('track %d, switched to new FILE, increased counter to %d',
                        trackNumber, counter)
                currentFile = File(filePath, start, length)
                #currentOffset += common.msfToFrames(start)
                currentLength += common.msfToFrames(length)

            # look for START lines
            m = _START_RE.search(line)
            if m:
                if not currentTrack:
                    self.message(number, 'START without preceding TRACK')
                    print 'ouch'
                    continue

                length = common.msfToFrames(m.group('length'))
                currentTrack.index(0, path=currentFile.path,
                    relative=currentOffset, counter=counter)
                self.debug('track %d, added index %r',
                    currentTrack.number, currentTrack.getIndex(0))
                # store the pregapLength to add it when we index 1 for this
                # track on the next iteration
                pregapLength = length
                
            # look for INDEX lines
            m = _INDEX_RE.search(line)
            if m:
                if not currentTrack:
                    self.message(number, 'INDEX without preceding TRACK')
                    print 'ouch'
                    continue

                indexNumber += 1
                offset = common.msfToFrames(m.group('offset'))
                currentTrack.index(indexNumber, path=currentFile.path,
                    relative=offset, counter=counter)
                self.debug('track %d, added index %r',
                    currentTrack.number, currentTrack.getIndex(indexNumber))

        # handle index 1 of final track, if any
        if currentTrack:
            currentTrack.index(1, path=currentFile.path,
                relative=currentOffset + pregapLength, counter=counter)
            self.debug('track %d, added index %r',
                currentTrack.number, currentTrack.getIndex(1))

    def message(self, number, message):
        """
        Add a message about a given line in the cue file.

        @param number: line number, counting from 0.
        """
        self._messages.append((number + 1, message))

    def getTrackLength(self, track):
        # returns track length in frames, or -1 if can't be determined and
        # complete file should be assumed
        # FIXME: this assumes a track can only be in one file; is this true ?
        i = self.table.tracks.index(track)
        if i == len(self.table.tracks) - 1:
            # last track, so no length known
            return -1

        thisIndex = track.indexes[1] # FIXME: could be more
        nextIndex = self.table.tracks[i + 1].indexes[1] # FIXME: could be 0

        c = thisIndex.counter
        if c is not None and c == nextIndex.counter:
            # they belong to the same source, so their relative delta is length
            return nextIndex.relative - thisIndex.relative

        # FIXME: more logic
        return -1

    def getRealPath(self, path):
        """
        Translate the .cue's FILE to an existing path.
        """
        if os.path.exists(path):
            return path

        # .cue FILE statements have Windows-style path separators, so convert
        tpath = os.path.join(*path.split('\\'))
        candidatePaths = []

        # if the path is relative:
        # - check relatively to the cue file
        # - check only the filename part relative to the cue file
        if tpath == os.path.abspath(tpath):
            candidatePaths.append(tPath)
        else:
            candidatePaths.append(os.path.join(
                os.path.dirname(self._path), tpath))
            candidatePaths.append(os.path.join(
                os.path.dirname(self._path), os.path.basename(tpath)))

        for candidate in candidatePaths:
            noext, _ = os.path.splitext(candidate)
            for ext in ['wav', 'flac']:
                cpath = '%s.%s' % (noext, ext)
                if os.path.exists(cpath):
                    return cpath

        raise KeyError, "Cannot find file for %s" % path

class File:
    """
    I represent a FILE line in a .toc file.
    """
    def __init__(self, path, start, length):
        self.path = path
        #self.start = start
        #self.length = length

    def __repr__(self):
        return '<File "%s">' % (self.path, )
