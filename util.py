# -*- coding: utf-8 -*-
"""
Miscellaneous utility functions.

------------------------------------------------------------------------------
Released under the Creative Commons CC0 1.0 Universal Public Domain Dedication.

@author      Erki Suurjaak
@created     16.02.2012
@modified    27.09.2015
------------------------------------------------------------------------------
"""
import base64
import collections
import ctypes
import fnmatch
import datetime
import imghdr
import io
import json
import locale
import logging
import math
import os
import re
import socket
import sqlite3
import struct
import subprocess
import sys
import time
import traceback
import urllib
import urllib2
import warnings
try: import ConfigParser as configparser   # Py2
except ImportError: import configparser    # Py3
try: import fcntl
except ImportError: fcntl = None  # Windows

try: from PIL import Image, ImageFile
except ImportError: Image = ImageFile = None
try: import wx
except ImportError: wx = None



# ---------------------------- Formatting routines ---------------------------

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


def format_exc(e):
    """Formats an exception as Class: message, or Class: (arg1, arg2, ..)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # DeprecationWarning on e.message
        msg = to_unicode(e.message) if getattr(e, "message", None) \
              else "(%s)" % ", ".join(map(to_unicode, e.args)) if e.args else ""
    result = u"%s%s" % (type(e).__name__, ": " + msg if msg else "")
    return result


def format_seconds(seconds, insert=""):
    """
    Returns nicely formatted seconds, e.g. "25 hours, 12 seconds".

    @param   insert  text inserted between count and unit, e.g. "4 call hours"
    """
    insert = insert + " " if insert else ""
    formatted = "0 %sseconds" % insert
    seconds = int(seconds)
    if seconds:
        formatted, inter = "", ""
        for unit, count in zip(["hour", "minute", "second"], [3600, 60, 1]):
            if seconds >= count:
                label = "%s%s" % (insert if not formatted else "", unit)
                formatted += inter + plural(label, seconds / count)
                seconds %= count
                inter = ", "
    return formatted


def plural(word, items=None, omitcount=False):
    """
    Returns the word as "count words", or "1 word" if count is 1,
    or "words" if count omitted.

    @param   items      item collection or count,
                        or None to get just the plural of the word
             omitcount  if true, count is omitted from final result
    """
    count = items or 0
    if hasattr(items, "__len__"):
        count = len(items)
    result = word + ("" if 1 == count else "s")
    if not (omitcount or items is None):
        result = "%s %s" % (count, result)
    return result


def round_float(value, precision=1):
    """
    Returns the float as a string, rounded to the specified precision and
    with trailing zeroes (and . if no decimals) removed.
    """
    return str(round(value, precision)).rstrip("0").rstrip(".")


def safedivf(a, b):
    """A zero-safe division, returns 0.0 if b is 0, a / float(b) otherwise."""
    return a / float(b) if b else 0.0


def to_int(value):
    """Returns the value as integer, or None if not integer."""
    try: return int(value)
    except ValueError: return None


def to_unicode(value, encoding=None):
    """
    Returns the value as a Unicode string. Tries decoding as UTF-8 if 
    locale encoding fails.
    """
    result = value
    if not isinstance(value, unicode):
        encoding = encoding or locale.getpreferredencoding()
        if isinstance(value, str):
            try:
                result = unicode(value, encoding)
            except Exception:
                result = unicode(value, "utf-8", errors="replace")
        else:
            result = unicode(str(value), errors="replace")
    return result



# ------------------------------- Time routines ------------------------------


def divide_delta(td1, td2):
    """Divides two timedeltas and returns the integer result."""
    us1 = td1.microseconds + 1000000 * (td1.seconds + 86400 * td1.days)
    us2 = td2.microseconds + 1000000 * (td2.seconds + 86400 * td2.days)
    # Integer division, fractional division would be float(us1) / us2
    return us1 / us2


def timedelta_seconds(timedelta):
    """Returns the total timedelta duration in seconds."""
    if hasattr(timedelta, "total_seconds"):
        result = timedelta.total_seconds()
    else:  # Python 2.6 compatibility
        result = timedelta.days * 24 * 3600 + timedelta.seconds + \
                 timedelta.microseconds / 1000000.
    return result


def get_locale_day_date(dt):
    """Returns a formatted (weekday, weekdate) in current locale language."""
    weekday, weekdate = dt.strftime("%A"), dt.strftime("%d. %B %Y")
    if locale.getpreferredencoding():
        for enc in (locale.getpreferredencoding(), "latin1"):
            try:
                weekday, weekdate = (x.decode(enc) for x in [weekday, weekdate])
                break
            except Exception: pass
    weekday = weekday.capitalize()
    return weekday, weekdate



# ----------------------- Collection handling routines -----------------------


def add_unique(lst, item, direction=1, maxlen=sys.maxint):
    """
    Adds the item to the list from start or end. If item is already in list,
    removes it first. If list is longer than maxlen, shortens it.

    @param   direction  side from which item is added, -1/1 for start/end
    @param   maxlen     maximum length list is allowed to grow to before
                        shortened from the other direction
    """
    if item in lst:
        lst.remove(item)
    lst.insert(0, item) if direction < 0 else lst.append(item)
    if len(lst) > maxlen:
        lst[:] = lst[:maxlen] if direction < 0 else lst[-maxlen:]
    return lst


def cmp_dicts(dict1, dict2):
    """
    Returns True if dict2 has all the keys and matching values as dict1.
    List values are converted to tuples before comparing.
    """
    result = True
    for key, v1 in dict1.items():
        result, v2 = key in dict2, dict2.get(key)
        if result:
            v1, v2 = (tuple(x) if isinstance(x, list) else x for x in [v1, v2])
            result = (v1 == v2)
        if not result:
            break  # break for key, v1
    return result


def get(collection, *path, **kwargs):
    """
    Returns the value at specified collection path. If path not available,
    returns the first keyword argument if any given, or None.
    Collection can be a nested structure of dicts, lists, tuples or strings.
    E.g. util.get({"root": {"first": [{"k": "v"}]}}, "root", "first", 0, "k").
    """
    default = (list(kwargs.values()) + [None])[0]
    result = collection if path else default
    for p in path:
        if isinstance(result, collections.Sequence):  # Iterable with index
            if isinstance(p, (int, long)) and p < len(result):
                result = result[p]
            else:
                result = default
        elif isinstance(result, collections.Mapping):  # Container with lookup
            result = result.get(p)
        else:
            result = default
        if result == default: break  # for p
    return result


def m(o, name, case=False):
    """Returns the members of the object or dict, filtered by name."""
    members = o.keys() if isinstance(o, dict) else dir(o)
    if case:
        return [i for i in members if name in i]
    else:
        return [i for i in members if name.lower() in i.lower()]


def recurse_data(data, keys, bucket=None, handler=None):
    """
    Performs a recursive search in data for values named by any key.
    If no such keys are present at root level, goes deeper into bucket values.
    If handler given, calls handler with each found value and key, otherwise
    returns the first found value.
    Both data and bucket contents can be dicts or lists or tuples.
    """
    if not isinstance(data, (dict, list, tuple)): return None
    datas = data if isinstance(data, (list, tuple)) else [data]
    for item in [x for x in datas if isinstance(x, dict)]:
        for key in keys:
            if key in item:
                if handler: handler(item, key)
                else: return item[key]
        if bucket in item: return recurse_data(item[bucket], keys, bucket)
    return None



# --------------------------- File and OS routines ---------------------------


def find_files(paths=(".",), wildcards=("*",), recursive=True, matchfunc=None):
    """Yields full filepaths matching wildcards under paths."""
    paths = [paths] if isinstance(paths, basestring) else paths
    wildcards = [wildcards] if isinstance(wildcards, basestring) else wildcards
    match = re.compile("|".join(map(fnmatch.translate, wildcards)), re.I).match
    if not wildcards: match = lambda x: True
    matchfunc = matchfunc or (lambda x: True)
    for path in paths:
        for root, dirs, files in os.walk(unicode(os.path.abspath(path))):
            for x in sorted(filter(match, files), key=lambda x: x.lower()):
                p = os.path.normpath(os.path.join(root, x))
                if os.path.isfile(p) and matchfunc(p): yield p
            if not recursive: break  # for root, dirs, files


def longpath(path):
    """Returns the path in long Windows form ("Program Files" not PROGRA~1)."""
    result = path
    try:
        buf = ctypes.create_unicode_buffer(65536)
        GetLongPathNameW = ctypes.windll.kernel32.GetLongPathNameW
        if GetLongPathNameW(unicode(path), buf, 65536):
            result = buf.value
        else:
            head, tail = os.path.split(path)
            if GetLongPathNameW(unicode(head), buf, 65536):
                result = os.path.join(buf.value, tail)
    except Exception: pass
    return result


def path_to_url(path, encoding="utf-8"):
    """
    Returns the local file path as a URL, e.g. "file:///C:/path/file.ext".
    """
    path = path.encode(encoding) if isinstance(path, unicode) else path
    if ":" not in path:
        # No drive specifier, just convert slashes and quote the name
        if path[:2] == "\\\\":
            path = "\\\\" + path
        url = urllib.quote("/".join(path.split("\\")))
    else:
        url, parts = "", path.split(":")
        if len(parts[0]) == 1:  # Looks like a proper drive, e.g. C:\
            url = "///" + urllib.quote(parts[0].upper()) + ":"
            parts = parts[1:]
        components = ":".join(parts).split("\\")
        for part in filter(None, components):
            url += "/" + urllib.quote(part)
    url = "file:%s%s" % ("" if url.startswith("///") else "///" , url)
    return url


def safe_filename(filename):
    """Returns the filename with characters like \:*?"<>| removed."""
    return re.sub(r"[\/\\\:\*\?\"\<\>\|]", "", filename)


def shorten_path(path, length=20):
    """Returns a shortened version of the path like 'C:/Prog../file.ext'."""
    result = path = path.encode("utf-8")
    if len(result) > length:
        result = "..%s%s" % (os.sep, os.path.split(result)[-1])
        result = "%s%s" % (path[:length - len(result)], result)
    if len(result) > length:
        result = ".." + result[2 - length:]
    return result


def start_file(filepath):
    """
    Tries to open the specified file in the operating system.

    @return  (success, error message)
    """
    success, error = True, ""
    try:
        if "nt" == os.name:
            try: os.startfile(filepath)
            except WindowsError as e:
                if 1155 == e.winerror:  # ERROR_NO_ASSOCIATION
                    cmd = "Rundll32.exe SHELL32.dll, OpenAs_RunDLL %s"
                    os.popen(cmd % filepath)
                else: raise
        elif "mac" == os.name:
            subprocess.call(("open", filepath))
        elif "posix" == os.name:
            subprocess.call(("xdg-open", filepath))
    except Exception as e:
        success, error = False, repr(e)
    return success, error


def unique_path(pathname):
    """
    Returns a unique version of the path. If a file or directory with the
    same name already exists, returns a unique version
    (e.g. "C:\config (2).sys" if ""C:\config.sys" already exists).
    """
    result = pathname
    path, name = os.path.split(result)
    base, ext = os.path.splitext(name)
    if len(name) > 255:  # Filesystem limitation
        name = base[:255 - len(ext) - 2] + ".." + ext
        result = os.path.join(path, name)
    counter = 2
    while os.path.exists(result):
        suffix = " (%s)%s" % (counter, ext)
        name = base + suffix
        if len(name) > 255:
            name = base[:255 - len(suffix) - 2] + ".." + suffix
        result = os.path.join(path, name)
        counter += 1
    return result


def win32_unicode_argv():
    """Returns sys.argv with Unicode characters under Windows."""
    # @from http://stackoverflow.com/a/846931/145400
    result = sys.argv
    from ctypes import POINTER, byref, cdll, c_int, windll
    from ctypes.wintypes import LPCWSTR, LPWSTR
 
    GetCommandLineW = cdll.kernel32.GetCommandLineW
    GetCommandLineW.argtypes = []
    GetCommandLineW.restype = LPCWSTR
 
    CommandLineToArgvW = windll.shell32.CommandLineToArgvW
    CommandLineToArgvW.argtypes = [LPCWSTR, POINTER(c_int)]
    CommandLineToArgvW.restype = POINTER(LPWSTR)
 
    argc = c_int(0)
    argv = CommandLineToArgvW(GetCommandLineW(), byref(argc))
    if argc.value:
        # Remove Python executable and commands if present
        start = argc.value - len(sys.argv)
        result = [argv[i].encode("utf-8") for i in range(start, argc.value)]
    return result



# ------------------------ Exception handling routines -----------------------


def ignore_error(func, e=Exception):
    """Wraps the function with a handler to ignore specified exceptions."""
    def inner(*args, **kwargs):
        try: return func(*args, **kwargs)
        except e: pass
    return inner


def try_until(func, count=1, sleep=0.5):
    """
    Tries to execute the specified function a number of times.

    @param    func   callable to execute
    @param    count  number of times to try (default 1)
    @param    sleep  seconds to sleep after failed attempts, if any
                     (default 0.5)
    @return          (True, func_result) if success else (False, None)
    """
    result, func_result, tries = False, None, 0
    while tries < count:
        tries += 1
        try: result, func_result = True, func()
        except Exception:
            time.sleep(sleep) if tries < count and sleep else None
    return result, func_result



# ----------------------------- Network routines -----------------------------


def get_ip():
    """Returns local machine's IP address."""
    result = next((x for x in socket.gethostbyname_ex(socket.gethostname())[2]
                   if not x.startswith("127.")), None)

    if not result:  # Try with UDP dummy broadcast socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.connect(("<broadcast>", 0))
            ip = sock.getsockname()[0]
            if not (ip.startswith("127.") or ip.startswith("0.")): result = ip
        except Exception: pass

    if not result and fcntl:  # Unix with only local name returns 127.x address
        for name in ("eth", "wlan", "wifi", "ath", "ppp"):
            for arg in (struct.pack("256s", name + str(i)) for i in range(3)):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    buf = fcntl.ioctl(sock.fileno(), 0x8915, arg) # SIOCGIFADDR
                    result = socket.inet_ntoa(buf[20:24])
                    break
                except IOError: pass

    return result


def urlpost(url, data=None, method="POST", timeout=5):
    """
    Posts data (as JSON if not string) to URL with method.

    @return   (response string, error string)
    """
    res, err = "", ""
    try:
        post = data if isinstance(data, (basestring, type(None))) else json_dumps(data)
        request = urllib2.Request(url, post)
        request.get_method = lambda: method
        res = urllib2.urlopen(request, timeout=timeout).read()
    except urllib2.HTTPError as e:
        err = e.read()
    except Exception:
        err = traceback.format_exc()
    return res, err



# ----------------------------- Logging routines -----------------------------


class MaxLevelFilter(logging.Filter):
    """Lets through all logging messages up to specified level."""
    def __init__(self, level): self.level = level
    def filter(self, record): return record.levelno <= self.level


class ModuleFilter(logging.Filter):
    """Filters logging from Python modules by exclusion or inclusion."""
    def __init__(self, exclude=None, include=None):
        self.exclude = exclude or []
        self.include = include or []

    def filter(self, record):
        return record.module not in self.exclude \
               and (not self.include or record.module in self.include)


def init_logging(level, stdlog=None, errlog=None, format=None, exclusions=None):
    """
    Initializes a system-wide logger with specified loglevel and filenames for
    standard and error logs.
    """
    if not format:
        format = "%(asctime)s\t%(levelname)s\t%(module)s:%(lineno)s\t%(message)s"
    logger = logging.getLogger()
    logger.setLevel(level)

    kws = dict(maxBytes=2**31, backupCount=2**31, encoding="utf-8", delay=True)

    if stdlog:
        defhandler = logging.handlers.RotatingFileHandler(stdlog, **kws)
        defhandler.setFormatter(logging.Formatter(format))
        defhandler.setLevel(logging.DEBUG)
        if errlog: defhandler.addFilter(MaxLevelFilter(logging.INFO))
        if exclusions: defhandler.addFilter(ModuleFilter(exclusions))
        logger.addHandler(defhandler)
    if errlog:
        errhandler = logging.handlers.RotatingFileHandler(errlog, **kws)
        errhandler.setFormatter(logging.Formatter("\n" + format))
        errhandler.setLevel(logging.WARN)
        logger.addHandler(errhandler)



# -------------------------- Configuration routines --------------------------

def ini_load(filename, obj=None):
    """
    Returns object with attributes loaded from INI file. Can be used to
    populate a configuration module: ini_load("conf.ini", module).
    A plain object is created if none given.
    """
    section, parts = "DEFAULT", filename.rsplit(":", 1)
    if len(parts) > 1 and os.path.isfile(parts[0]): filename, section = parts
    if not os.path.isfile(filename): return

    obj = obj if obj is not None else type("", (), {})()
    parser = configparser.RawConfigParser()
    parser.optionxform = str  # Force case-sensitivity on names
    try:
        def parse_value(raw):
            try: return json_loads(raw)  # Try to interpret as JSON
            except ValueError: return raw  # JSON failed, fall back to raw
        txt = open(filename).read()  # Add DEFAULT section if none present
        if not re.search("\\[\w+\\]", txt): txt = "[DEFAULT]\n" + txt
        parser.readfp(io.BytesIO(txt), filename)
        for k, v in parser.items(section): setattr(obj, k, parse_value(v))
    except Exception:
        logging.warn("Error reading config from %s.", filename, exc_info=True)
    return obj


def ini_save(filename, obj, attrs=None):
    """Saves object properties into INI file, all attributes or specified."""
    section = "*"
    parser = configparser.RawConfigParser()
    parser.optionxform = str  # Force case-sensitivity on names
    parser.add_section(section)
    try:
        f = open(filename, "wb")
        f.write("# Configuration written on %s.\n" % (
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        for name in sorted(attrs or vars(obj)):
            try: parser.set(section, name, json_dumps(getattr(obj, name)))
            except Exception: pass
        parser.write(f)
        f.close()
    except Exception:
        pass  # Fail silently



# ------------------------- JSON and SQLite routines -------------------------


def decode_b64_mime(string):
    """
    Returns a buffer containing Base64-decoded data, if string starts like
    'data:image/png,base64,iVBOR..'.
    """
    result = string
    match = re.match(r"(data:[^\\]+/[^,]+),base64,(.+)", string)
    if match:
        try:
            result = buffer(base64.b64decode(match.group(2)))
        except Exception:
            logging.exception("Error decoding '%s'.", match.group(1))
    return result


def encode_b64_mime(buf):
    """Returns the buffer/string data like 'data:image/png,base64,iVBOR..'."""
    subtype = imghdr.what(file=None, h=buf)
    media = "image" if subtype else "application"
    subtype = subtype or "octet-stream"
    result = "data:%s/%s,base64,%s" % (media, subtype, base64.b64encode(buf))
    return result


def json_dumps(data, indent=2, sort_keys=True):
    """
    Serializes to JSON, with datetime types converted to ISO 8601 format,
    and buffers converted to 'data:MEDIATYPE/SUBTYPE,base64,B64DATA'.
    """
    dateencoder = lambda x: hasattr(x, "isoformat") and x.isoformat()
    binaryencoder = lambda x: isinstance(x, buffer) and encode_b64_mime(x)
    encoder = lambda x: dateencoder(x) or binaryencoder(x)
    return json.dumps(data, default=encoder, indent=indent, sort_keys=sort_keys)


def json_loads(data):
    """
    Deserializes from JSON, with datetime strings converted to datetime objects,
    and strings with Base64 MIME header converted to decoded buffers.
    """
    decoder = lambda x: recursive_decode(x, [parse_datetime, decode_b64_mime])
    return json.loads(data, object_hook=decoder) if data else ""


def parse_datetime(string):
    """Tries to parse string as ISO8601 datetime."""
    result = string
    DT_FORMATS = [
        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d%H:%M:%S.%fZ", "%Y-%m-%d%H:%M:%S.%f", "%Y-%m-%d%H:%M:%S",
        "%Y%m%d%H%M%S%f", "%Y%m%d%H%M%S"
    ] if 14 < len(string) < 40 else []
    for fmt in DT_FORMATS:
        try: result = datetime.datetime.strptime(string, fmt); break
        except ValueError: pass
    return result


def recursive_decode(d, decoders):
    """Recursively converts strings in the collection with given decoders."""
    if isinstance(d, list):
        pairs = enumerate(d)
    elif isinstance(d, dict):
        pairs = d.items()
    result = []
    for k, v in pairs:
        if isinstance(v, basestring):
            v = next((x for x in (x(v) for x in decoders) if x != v), v)
        elif isinstance(v, (dict, list)):
            v = recursive_decode(v, decoders)
        result.append((k, v))
    if isinstance(d, list):
        return [x[1] for x in result]
    elif isinstance(d, dict):
        return dict(result)


def sqlite_adapt(types=("JSON", "TIMESTAMP")):
    """Adds autoconversion support to SQLite for JSON and TIMESTAMP columns."""
    types = [x.upper() for x in types]
    if "JSON" in types:
        [sqlite3.register_adapter(x, json_dumps) for x in (dict, list, tuple)]
        [sqlite3.register_converter(x, json_loads) for x in "json", "JSON"]
    if "TIMESTAMP" in types:
        sqlite3.register_converter("timestamp", parse_datetime)
        sqlite3.register_converter("TIMESTAMP", parse_datetime)



# ---------------------- Image routines, using PIL or wx ---------------------


def img_pil_resize(img, size, aspect_ratio=True, bg=(255, 255, 255)):
    """
    Returns a resized PIL.Image, centered if aspect ratio rescale resulted in 
    free space on one axis.
    """
    result = img
    if size and list(size) != list(result.size):
        size2, align_pos = list(size), None
        if result.size[0] < size[0] and img.size[1] < size[1]:
            size2 = result.size
            align_pos = [(a - b) / 2 for a, b in zip(size, size2)]
        elif aspect_ratio:
            ratio = safedivf(*result.size[:2])
            size2[ratio > 1] *= ratio if ratio < 1 else 1 / ratio
            align_pos = [(a - b) / 2 for a, b in zip(size, size2)]
        if result.size[0] > size[0] or result.size[1] > size[1]:
            result.thumbnail(tuple(map(int, size2)), Image.ANTIALIAS)
        if align_pos:
            result, result0 = Image.new(img.mode, size, bg), result
            result.paste(result0, tuple(map(int, align_pos)))
    return result


def img_recode(raw, format="PNG", size=None, aspect_ratio=True):
    """Recodes and/or resizes the raw image, using wx or PIL."""
    result = raw
    if wx:
        img = wx.ImageFromStream(io.BytesIO(raw))
        if size: img = img_wx_resize(img, size, aspect_ratio)
        result = img_wx_to_raw(img, format)
    elif ImageFile:
        imgparser = ImageFile.Parser(); imgparser.feed(raw)
        img = imgparser.close()
        if size: img = img_pil_resize(img, size, aspect_ratio)
        stream = io.BytesIO()
        img.save(stream, format)
        result = stream.getvalue()
    return result


def img_size(raw):
    """Returns the size of the as (width, height), using wx or PIL."""
    result = None
    if wx:
        result = tuple(wx.ImageFromStream(io.BytesIO(raw)).GetSize())
    elif ImageFile:
        imgparser = ImageFile.Parser(); imgparser.feed(raw)
        result = tuple(imgparser.close().size)
    return result


def img_wx_resize(img, size, aspect_ratio=True, bg=(255, 255, 255)):
    """
    Returns a resized wx.Image or wx.Bitmap, centered if aspect ratio rescale
    resulted in free space on one axis.
    """
    result = img if isinstance(img, wx.Image) else img.ConvertToImage()
    if size:
        size1, size2 = list(result.GetSize()), list(size)
        if size2 != size1:
            align_pos = None
            if size1[0] < size[0] and size1[1] < size[1]:
                size2 = tuple(size1)
                align_pos = [(a - b) / 2 for a, b in zip(size, size2)]
            elif aspect_ratio:
                ratio = safedivf(*size1[:2])
                size2[ratio > 1] *= ratio if ratio < 1 else 1 / ratio
                align_pos = [(a - b) / 2 for a, b in zip(size, size2)]
            if size1[0] > size[0] or size1[1] > size[1]:
                result = result.ResampleBox(*size2)
            if align_pos:
                result.Resize(size, align_pos, *bg)
    return result


def img_wx_to_raw(img, format="PNG"):
    """Returns the wx.Image or wx.Bitmap as raw data of specified type."""
    stream = io.BytesIO()
    img = img if isinstance(img, wx.Image) else img.ConvertToImage()
    fmttype = getattr(wx, "BITMAP_TYPE_" + format.upper(), wx.BITMAP_TYPE_PNG)
    img.SaveStream(stream, fmttype)
    result = stream.getvalue()
    return result
