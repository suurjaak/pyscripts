# -*- coding: utf-8 -*-
"""
Shifts subtitle timestamps in an SRT file by a given amount.

@param       subtitle filename
@param       seconds to shift subtitles by, can be negative

------------------------------------------------------------------------------
Released under the Creative Commons CC0 1.0 Universal Public Domain Dedication.

@author      Erki Suurjaak
@created     16.04.2015
@modified    20.10.2015
------------------------------------------------------------------------------
"""
import datetime
import re
import sys

USAGE = ("usage: %s SUBTITLEFILE SECONDS\n\nShifts subtitle timestamps in "
         "an SRT file by a given amount." % sys.argv[0])

def shift_subtitles(filename, delta, filename2):
    """Reads in SRT file, applies timedelta, and writes out to second file."""
    NULLDELTA = datetime.timedelta()
    # Timestamp line is like "00:01:13,738 --> 00:01:16,230"
    rgx = re.compile("%s --> %s" % ((r"(\d{2})\:(\d{2})\:(\d{2})\,(\d{3})",) * 2))
    with open(filename) as f: lines = list(f)
    with open(filename2, "w") as g:
        for line in lines:
            line2, match = line, rgx.search(line)
            for i in range(2 if match else 0):
                h, m, s, ms = map(int, match.groups()[4*i:4*(i+1)])
                t = max(delta + datetime.timedelta(hours=h, minutes=m, seconds=s,
                        milliseconds=ms), NULLDELTA)
                line2 = "%s%02d:%02d:%02d,%03d%s" % (line2 if i else "", 
                         t.seconds / 3600, t.seconds / 60 % 60, t.seconds % 60,
                         t.microseconds / 1000, "\n" if i else " --> ")
            g.write(line2)



if "__main__" == __name__:
    if len(sys.argv) < 3 or "-h" in sys.argv or "--help" in sys.argv:
        sys.exit(USAGE)
    filename, seconds = sys.argv[1], float(sys.argv[2])
    shift_subtitles(filename, datetime.timedelta(seconds=seconds), filename)
