# -*- coding: utf-8 -*-
"""
Counts bits (0/1 ratio) in file system files, prints statistics by file type.
Retains a local SQLite database as cache.

------------------------------------------------------------------------------
Released under the Creative Commons CC0 1.0 Universal Public Domain Dedication.

@author      Erki Suurjaak
@created     04.10.2012
@modified    23.09.2015
"""
from __future__ import print_function
import argparse
import codecs
import fnmatch
import inspect
import math
import os
import re
import sqlite3
import sys

SCRIPT_PATH = os.path.abspath(inspect.getfile(inspect.currentframe()))
ARGUMENTS = {
    "description": "Count the bits (0/1 ratio) in file system files.",
    "arguments": [
        {"args": ["wildcards"], "nargs": "*", "metavar": "WILDCARD",
         "help": "one or more filename patterns to match"},
        {"args": ["-d", "--directory"], "nargs": "+", "dest": "dirs",
         "metavar": "DIR", "default": ["/"],
         "help": "directories to process, filesystem root by default"},
        {"args": ["-nr", "--nonrecursive"], "dest": "nonrecursive",
         "action": "store_true", "help": "skip subdirectories"},
        {"args": ["-s", "--statsonly"],
         "action": "store_true", "dest": "statsonly",
         "help": "show accumulated statistics and exit"},
        {"args": ["--db"], "dest": "dbpath",
         "default": os.path.join(os.path.dirname(SCRIPT_PATH), "countbits.db"),
         "help": "cache-database path, by default in program directory. "
                 "Use :memory: or empty string for no caching."},
    ],
}
CHAR_HIGHBITS = dict((chr(i), 0) for i in range(256))  # {char: 1-bit count}
for i in range(len(CHAR_HIGHBITS)):
    CHAR_HIGHBITS[chr(i)] = (i & 1) + CHAR_HIGHBITS[chr(i >> 1)]
DB_INITSQL = ("CREATE TABLE IF NOT EXISTS files (path TEXT NOT NULL PRIMARY KEY, "
              "extension TEXT, zeroes INTEGER, ones INTEGER, mtime INTEGER, "
              "dt TIMESTAMP DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'now')))")



def find_files(paths=(".",), wildcards=("*",), recursive=True):
    """Yields full filepaths matching wildcards under paths."""
    paths = [paths] if isinstance(paths, basestring) else paths
    wildcards = [wildcards] if isinstance(wildcards, basestring) else wildcards
    match = re.compile("|".join(map(fnmatch.translate, wildcards)), re.I).match
    if not wildcards: match = lambda x: True
    for path in paths:
        for root, dirs, files in os.walk(unicode(os.path.abspath(path))):
            for x in sorted(filter(match, files), key=lambda x: x.lower()):
                filepath = os.path.normpath(os.path.join(root, x))
                if os.path.isfile(filepath): yield filepath
            if not recursive: break # for root, dirs, files


def get_filebits(filepath, BLOCKSIZE=81920):
    """Returns (zerobit-count, onebit-count) for the specified file."""
    zeroes, ones = 0, 0
    try:
        with open(filepath, "rb") as f:
            data = f.read(BLOCKSIZE)
            while data:
                count = sum(CHAR_HIGHBITS[x] for x in data)
                ones, zeroes = ones + count, zeroes + 8 * len(data) - count
                data = f.read(BLOCKSIZE)
    except EnvironmentError: pass
    return zeroes, ones


def format_bytes(size, precision=2, inter=" "):
    """Returns a formatted byte size (e.g. 421.45 MB)."""
    result = "0 bytes"
    if size:
        UNITS = [("bytes", "byte")[1 == size]] + [x + "B" for x in "KMGTPEZY"]
        exponent = min(int(math.log(size, 1024)), len(UNITS) - 1)
        result = "%.*f" % (precision, size / (1024. ** exponent))
        result += "" if precision > 0 else "."  # 0-precision has no separator
        result = result.rstrip("0").rstrip(".") + inter + UNITS[exponent]
    return result


def shorten_path(path, length=20):
    """Returns a shortened version of the path like 'C:/Prog../file.ext'."""
    result = path = path.encode("utf-8")
    if len(result) > length:
        result = "..%s%s" % (os.sep, os.path.split(result)[-1])
        result = "%s%s" % (path[:length - len(result)], result)
    if len(result) > length:
        result = ".." + result[2 - length:]
    return result


def print_progress(totals, filepath):
    """Prints out current progress and running stats."""
    bits = float(totals["zeroes"] + totals["ones"])
    safediv = lambda a, b: a/b if b else 0
    t = "\rFiles: {0:>7,d}   Size: {1:>7}   Zeroes/ones: {2: 3.0%} vs {3: 3.0%}   {4}"
    print(t.format(totals["files"], format_bytes(bits / 8, 1, ""),
          safediv(totals["zeroes"], bits), safediv(totals["ones"], bits),
          shorten_path(filepath, 16)), end=" ")


def print_stats(db):
    """Prints out complete accumulated statistics."""
    stats, totals = {}, {}
    sql1 = ("SELECT COUNT(*) AS files, COALESCE(SUM(zeroes), 0) "
            "AS zeroes, COALESCE(SUM(ones), 0) AS ones FROM files")
    sql2 = ("SELECT extension, COUNT(*) AS files, "
            "COALESCE(SUM(zeroes), 0) AS zeroes, "
            "COALESCE(SUM(ones), 0) AS ones FROM files GROUP BY extension")
    for x in db.execute(sql1): totals.update(x)
    for x in db.execute(sql2): stats[x["extension"]] = dict(x)
    safediv = lambda a, b: a/b if b else 0

    bits = float(totals["zeroes"] + totals["ones"])
    byteslen, fileslen = map(len, map("{:,.0f}".format, [bits / 8, totals["files"]]))
    t = u"{0:>14}   {1:>4s} vs {2:>4s}   {3:>{byteslen},.0f} bytes   {4:>{fileslen},} files"
    print("\n\n" + t.format("TOTAL ZERO/ONE",
          "{:.0%}".format(safediv(totals["zeroes"], bits)),
          "{:.0%}".format(safediv(totals["ones"], bits)), bits / 8,
          totals["files"], byteslen=byteslen, fileslen=fileslen))
    print("-" * 79)

    t = u"{0:>14}   {1:>4s} vs {2:>4s}   {3:>{byteslen},.0f} bytes   {4:>{fileslen},} ({5:>2s} size)"
    for ext, data in sorted(stats.items(), key=lambda x: -(x[1]["ones"] + x[1]["zeroes"])):
        extbits = float(data["zeroes"] + data["ones"])
        print(t.format(("." + ext) if ext else "<NO EXTENSION>",
              "{:.0%}".format(data["zeroes"] / extbits),
              "{:.0%}".format(data["ones"] / extbits),
              extbits / 8, data["files"], "{:.0%}".format(extbits / bits),
              byteslen=byteslen, fileslen=fileslen))


def countbits(paths=("/",), wildcards=("*",), recursive=True,
              dbpath=":memory:", statsonly=False):
    """Processes detected files for bitcount, prints statistics."""
    db = sqlite3.connect(dbpath, isolation_level=None)  # Auto-commit
    db.execute(DB_INITSQL)
    db.row_factory = sqlite3.Row

    if statsonly: return print_stats(db)

    dbfiles = dict((x["path"], dict(x)) for x in db.execute("SELECT * FROM files"))
    totals = {"zeroes": 0, "ones": 0, "files": 0}
    for x in db.execute("SELECT COUNT(*) AS files, COALESCE(SUM(zeroes), 0) "
                        "AS zeroes, COALESCE(SUM(ones), 0) AS ones FROM files"):
        totals.update(x)

    def is_skippable(p, mtime, size):
        """Returns whether to skip the file for bitcount processing."""
        result = not bool(size)
        if p in dbfiles:
            lastsize = (dbfiles[p]["zeroes"] + dbfiles[p]["ones"]) / 8
            result = (mtime == dbfiles[p]["mtime"] and size == lastsize)
            if not result:
                db.execute("DELETE FROM files WHERE path = ?", [p])
                for k in "zeroes", "ones", "files": 
                    totals[k] -= dbfiles[p].get(k, 1)
        return result

    try:
        for filepath in find_files(paths, wildcards, recursive):
            mtime, size = os.path.getmtime(filepath), os.path.getsize(filepath)
            if is_skippable(filepath, mtime, size): continue # for filepath
            print_progress(totals, filepath)
            zeroes, ones = get_filebits(filepath)
            if not (zeroes or ones): continue # for filepath

            ext = os.path.splitext(filepath)[1][1:].lower()
            db.execute("INSERT INTO files (path, extension, zeroes, ones, mtime) "
                       "VALUES (?, ?, ?, ?, ?)", [filepath, ext, zeroes, ones, mtime])
            for k, v in ("zeroes", zeroes), ("ones", ones), ("files", 1):
                totals[k] += v
            print_progress(totals, filepath)
    except KeyboardInterrupt: pass
    finally:
        print_stats(db)



if "__main__" == __name__:
    parser = argparse.ArgumentParser(description=ARGUMENTS["description"])
    for a in ARGUMENTS["arguments"]: parser.add_argument(*a.pop("args"), **a)
    args = parser.parse_args()
    args.paths, args.recursive = args.dirs, not args.nonrecursive
    del args.nonrecursive; del args.dirs

    enc = sys.stdout.encoding or "utf-8"
    sys.stdout = codecs.getwriter(enc)(sys.stdout, errors="replace")
    countbits(**vars(args))
