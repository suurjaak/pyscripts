#-*- coding: utf-8 -*-
"""
Lists files having the same content.

------------------------------------------------------------------------------
Released under the Creative Commons CC0 1.0 Universal Public Domain Dedication.

@author      Erki Suurjaak
@created     23.02.2015
@modified    23.09.2015
"""
import argparse
import codecs
import collections
import fnmatch
import math
import os
import re
import sys

TYPEGROUPS = {
    "audio": ["*." + x for x in "aac aif aifc aiff alac ape au flac m4a mp1 "
              "mp3 oga ra ram wav wma".split()],
    "image": ["*." + x for x in "bmp gif jfif jpg jpeg png".split()],
    "video": ["*." + x for x in "3gp 3gpp asf avi divx f4v flv m1s m2s m2v "
              "m4v mkv mov mp2v mp4 mp7 mpe mpeg mpg ogm qt ram rm rmvb vob "
              "wbmp webm wmv".split()],
}
ARGUMENTS = {
    "description": "List files having the same content.",
    "arguments": [
        {"args": ["wildcards"], "nargs": "*", "metavar": "WILDCARD",
         "help": "one or more filename patterns to match"},
        {"args": ["-d", "--directory"], "nargs": "+", "dest": "dirs",
         "metavar": "DIR", "default": [os.getcwd()],
         "help": "directories to process, defaults to working directory"},
        {"args": ["-t", "--type"], "nargs": "+", "dest": "types",
         "choices": TYPEGROUPS, "metavar": "", 
         "help": "file types to match (%s)" % ", ".join(TYPEGROUPS)},
        {"args": ["-r", "--recursive"], "help": "process subdirectories",
         "action": "store_true", "dest": "recursive"},
        {"args": ["-s", "--sizeonly"], "help": "match by file size only",
         "action": "store_true", "dest": "sizeonly"},
    ],
}


def find_duplicates(paths, wildcards=("*",), recursive=False, sizeonly=False):
    """Yields duplicate files as (size, [files])."""
    files = find_files(paths, wildcards, recursive)
    sizes = collections.defaultdict(list)
    for f, size in ((f, pathhandler(os.path.getsize)(f)) for f in files):
        sizes[size].append(f)
    for size, ff in sizes.items():
        if len(ff) < 2: sizes.pop(size)

    for size, sizefiles in sorted(sizes.items(), key=lambda (s, ff): -s):
        filesets = [sizefiles] if sizeonly else compare_files(sizefiles)
        for dupes in (x for x in filesets if len(x) > 1):
            dupes = sorted(dupes, key=lambda x: x.lower())
            if len(paths) == 1:
                dupes = [x.replace(paths[0], "").lstrip("\\/") for x in dupes]
            yield (size, dupes)


def find_files(paths=(".",), wildcards=("*",), recursive=True):
    """Returns a list of full filepaths matching wildcards under paths."""
    paths = [paths] if isinstance(paths, basestring) else paths
    wildcards = [wildcards] if isinstance(wildcards, basestring) else wildcards
    result = []
    match = re.compile("|".join(map(fnmatch.translate, wildcards)), re.I).match
    if not wildcards: match = lambda x: True
    for path in paths:
        for root, dirs, files in os.walk(unicode(os.path.abspath(path))):
            files = [os.path.join(root, x) for x in files if match(x)]
            files = map(os.path.normpath, files)
            result.extend(filter(pathhandler(os.path.isfile), files))
            if not recursive: break # for root, dirs, files
    return result


def compare_files(filepaths, BLOCKSIZE=81920):
    """
    Checks which of the specified files have the same content.

    @param   filepaths  a list of file paths to process
    @return             [[file paths of identical content], ]
    """
    if len(filepaths) < 2: return [filepaths]
    result, branches = [], [list(filepaths)]
    streams = dict((p, pathhandler(open)(p, "rb")) for p in filepaths)
    # Files get divided into separate branches as content starts to differ.
    while branches:
        for paths in list(branches):
            blocks, pathmap = [streams[p].read(BLOCKSIZE) for p in paths], {}
            for i, block in enumerate(blocks):
                pathmap[block] = pathmap.get(block, []) + [paths[i]]
            for block, count in collections.Counter(blocks).items():
                if not block or count != len(blocks):
                    for p in pathmap[block]: paths.remove(p)
                    target = branches if block and count > 1 else result
                    target.append(pathmap[block])
            if not paths: branches.remove(paths)
    for f in streams.values(): f.close()
    return result


def pathhandler(func):
    """Wraps the OS function with a handler for long filenames on Windows."""
    def inner(filename, *args, **kwargs):
        try: return func(filename, *args, **kwargs)
        except EnvironmentError:
            if len(filename) < 255 or "nt" != os.name: raise
            return func(r"\\?\\" + filename, *args, **kwargs)
    return inner


def format_bytes(size, precision=2, inter=" "):
    """Returns a formatted byte size (e.g. 421.45 MB)."""
    result = "0 bytes"
    if size:
        UNITS = [("bytes", "byte")[1 == size]] + [x + "B" for x in "KMGTPEZY"]
        exponent = min(int(math.log(size, 1024)), len(UNITS) - 1)
        result = "%.*f" % (precision, size / (1024. ** exponent))
        result += "" if precision > 0 else "."  # Do not strip integer zeroes
        result = result.rstrip("0").rstrip(".") + inter + UNITS[exponent]
    return result


if "__main__" == __name__:
    parser = argparse.ArgumentParser(description=ARGUMENTS["description"])
    for a in ARGUMENTS["arguments"]: parser.add_argument(*a.pop("args"), **a)
    args = parser.parse_args()
    for filetype in args.types or []: args.wildcards += TYPEGROUPS[filetype]
    args.paths = args.dirs; del args.dirs; del args.types

    enc = sys.stdout.encoding or "utf-8"
    sys.stdout = codecs.getwriter(enc)(sys.stdout, errors="replace")
    results = [] # [(size, files), ]
    try:
        for size, files in find_duplicates(**vars(args)):
            if not results: print("\nDuplicate files:")
            results += [(size, files)]
            print("%s [%s]:\n  %s" % (format_bytes(size), len(files),
                  "\n  ".join(files)))
    finally:
        print("\nDuplicates in total: %s, with %s of content." % (
              sum(len(ff) for s, ff in results),
              format_bytes(sum(s * len(ff) for s, ff in results))))
