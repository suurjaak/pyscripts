#-*- coding: utf-8 -*-
"""
Invokes Media Player Classic to create thumbnails for video files in the
current directory. Videos with existing matching image files are skipped.
Windows-only, requires pywin32.

@param       video filenames or wildcards, if any

------------------------------------------------------------------------------
Released under the Creative Commons CC0 1.0 Universal Public Domain Dedication.

@author      Erki Suurjaak
@created     06.05.2012
@modified    17.10.2015
"""
import codecs
import ctypes
import datetime
import fnmatch
import os
import re
import shutil
import subprocess
import sys
import uuid
import win32api
import win32com.client
import win32con
import win32gui
import win32gui_struct
import win32process


TEMP_DIR = os.path.join(os.getenv("SYSTEMDRIVE"), os.sep)
TYPEGROUPS = {
    "image": ["*." + x for x in "bmp gif jfif jpg jpeg png".split()],
    "video": ["*." + x for x in "3gp 3gpp asf avi divx f4v flv m1s m2s m2v "
              "m4v mkv mov mp2v mp4 mp7 mpe mpeg mpg ogm qt ram rm rmvb vob "
              "wbmp webm wmv".split()],
}
USAGE = ("usage: %s [WILDCARD [WILDCARD ...]]\n\nCreates thumbnails for videos"
         " in current directory, using Media Player Classic." % sys.argv[0])
MPC_CLASS = "MediaPlayerClassicW"

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


def ignore_error(func, e=Exception):
    """Wraps the function with a handler to ignore specified exceptions."""
    def inner(*args, **kwargs):
        try: return func(*args, **kwargs)
        except e: pass
    return inner


def get_mpc():
    """Returns Media Player Classic executable path from Start Menu links."""
    linkpaths = [os.path.join(os.getenv(x) or "", "Start Menu", "Programs")
                 for x in "ALLUSERSPROFILE", "HOME"]
    wildcards = ["*Media Player Classic*", "*MPC-HC*"]
    for shortcut in find_files(linkpaths, wildcards):
        shell = win32com.client.Dispatch("WScript.Shell")
        path = shell.CreateShortCut(shortcut).TargetPath
        if all(x.endswith(".exe") and "unins" not in x
               and os.path.isfile(x) for x in [path.lower()]):
            return path


def get_handle(classname=None, title=None, pid=None):
    """
    Returns the handle of a Windows program window specified by the
    classname (like "MediaPlayerClassicW") or title or process ID.
    """
    result = []
    title = title and title.encode(sys.getfilesystemencoding())
    args = classname, title, pid
    def enumhandler(hwnd, lst):
        cls, ttl = get_classname(hwnd), win32gui.GetWindowText(hwnd)
        thread_id, proc_id = win32process.GetWindowThreadProcessId(hwnd)
        if all(x == y for x, y in zip(args, [cls, ttl, proc_id]) if x):
            lst.append(hwnd)
    win32gui.EnumWindows(enumhandler, result)
    return result.pop() if result else None


def get_classname(hwnd):
    """Returns the class name of the specified window handle."""
    name = ctypes.c_buffer("\x00" * 32)
    ctypes.windll.user32.GetClassNameA(hwnd, name, len(name))
    return name.value


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


def create_thumb(videofile, imagefile, cmd):
    """Generates thumbnails file from video by feeding keypresses to player."""
    lastwindow = win32gui.GetActiveWindow()
    proc = subprocess.Popen("%s \"%s\"" % (cmd, videofile))

    dt = datetime.datetime.now()
    while not (get_handle(pid=proc.pid)
    or datetime.datetime.now() - dt > datetime.timedelta(seconds=10)):
        win32api.Sleep(100)
    ignore_error(win32gui.SetActiveWindow)(lastwindow)

    try:
        # Move window to top right corner
        win32api.Sleep(500)  # Allow time for UI to become responsive
        hwnd = get_handle(pid=proc.pid, classname=MPC_CLASS)
        if not hwnd: 
            return
        rect = win32gui.GetWindowRect(hwnd)
        x = win32api.GetSystemMetrics(0) - (rect[2] - rect[0])
        win32gui.MoveWindow(hwnd, x, 0, 1, 1, 1) # hwnd, x, y, w, h, bRepaint

        # Open "Save as" dialog by activating the thumbnails entry in File-menu
        appmenu = win32gui.GetMenu(hwnd)
        filemenu = win32gui.GetSubMenu(appmenu, 0)
        for i in range(win32gui.GetMenuItemCount(filemenu)):
            buf, extras = win32gui_struct.EmptyMENUITEMINFO()
            win32gui.GetMenuItemInfo(filemenu, i, True, buf)
            menuitem = win32gui_struct.UnpackMENUITEMINFO(buf)
            if menuitem.text and "thumbnails" in menuitem.text.lower():
                win32api.PostMessage(hwnd, win32con.WM_COMMAND, menuitem.wID, 0)
                break # for i
        win32api.Sleep(500)  # Give dialog time to open


        # Get dialog handle
        windows = []
        def enumhandler(hwnd, lst):
            lst.append((hwnd, get_classname(hwnd), win32gui.GetParent(hwnd)))
        win32gui.EnumWindows(enumhandler, windows)
        dialog_hwnd = next((h for h, c, p in windows if "#32770" == c and hwnd == p), None)

        # Get dialog children handles and filename editbox handle
        components = []
        def enumchildhandler(hwnd, lst):
            lst.append((hwnd, get_classname(hwnd)))
        win32gui.EnumChildWindows(dialog_hwnd, enumchildhandler, components)
        file_hwnd = max((h for h, c in components if "Edit" == c),
            key=lambda h: win32api.SendMessage(h, win32con.WM_GETTEXT, 1000, ""))

        # Set file type to JPG
        win32api.PostMessage(file_hwnd, win32con.WM_KEYDOWN, win32con.VK_TAB, 0)
        for x in (h for h, c in components if "ComboBox" == c):
            win32api.PostMessage(x, win32con.WM_KEYDOWN, ord("J"), 0)

        # Empty filename editbox contents
        for i in range(win32api.SendMessage(file_hwnd, win32con.WM_GETTEXT, 1000, "")):
            win32api.PostMessage(file_hwnd, win32con.WM_KEYDOWN, win32con.VK_DELETE, 0)
            win32api.PostMessage(file_hwnd, win32con.WM_KEYDOWN, win32con.VK_BACK, 0)
        # Fill filename
        for c in imagefile:
            win32api.PostMessage(file_hwnd, win32con.WM_IME_CHAR, ord(c), 0)
        win32api.PostMessage(file_hwnd, win32con.WM_CHAR, win32con.VK_RETURN, 0)

        # Close dialog
        shell = win32com.client.Dispatch("WScript.Shell")
        win32gui.SetActiveWindow(dialog_hwnd)
        shell.SendKeys("{ENTER}")  # Only way to feed Return to dialog

        # Wait for image file to be created and written out in full
        dt = datetime.datetime.now()
        while (proc.returncode is None
        and not (os.path.exists(imagefile) and os.path.getsize(imagefile))
        and datetime.datetime.now() - dt < datetime.timedelta(seconds=20)):
            win32api.Sleep(50)
        win32api.Sleep(200)  # Give player time to finalize
    finally:
        proc.terminate()


def make_thumbnails(files, thumbfunc):
    """
    For any file without a matching image file, invokes function to generate
    a thumbnail image.
    """
    dirs_changed = {}  # {path name: os.stat_result}
    imageexts = [x.replace("*", "") for x in TYPEGROUPS["image"]]
    for video in files:
        path, tail = os.path.split(video)
        base = os.path.splitext(tail)[0]
        if any(os.path.isfile(os.path.join(path, base + x)) for x in imageexts):
            continue  # for video

        pathstat = dirs_changed.get(path) or os.stat(path)
        image = os.path.join(path, base + ".jpg")
        tempimage = os.path.join(TEMP_DIR, uuid.uuid4().hex[:8] + ".jpg")
        if os.path.exists(tempimage): os.remove(tempimage)
        print("Creating thumb for video \"%s\"." % video)
        attempts = 3
        while attempts:
            try:
                thumbfunc(video, tempimage), shutil.move(tempimage, image)
                break  # while attempts
            except Exception:
                attempts -= 1
        if os.path.exists(image):
            shutil.copystat(video, image)  # Set video file timestamps to image
            dirs_changed[path] = pathstat
        else:
            print("Failed to produce \"%s\"." % image)
    for path, stat in dirs_changed.items():  # Restore directory timestamps
        os.utime(path, (stat.st_atime, stat.st_mtime))



if "__main__" == __name__:
    mpc = get_mpc()
    if not mpc: sys.exit("Could not locate Media Player Classic shortcut.")
    if "-h" in sys.argv or "--help" in sys.argv:
        sys.exit(USAGE)

    cmd = "\"%s\" /new /open /fixedsize 1, 1" % mpc
    make_thumb = lambda video, image: create_thumb(video, image, cmd)
    wildcards = win32_unicode_argv()[1:] or TYPEGROUPS["video"]
    # If user-specified wildcards, ensure that only video files get selected
    matchfunc = None if not sys.argv[1:] else re.compile("|".join(
                map(fnmatch.translate, TYPEGROUPS["video"])), re.I).match
    videos = find_files(os.getcwdu(), wildcards, False, matchfunc)
    enc = sys.stdout.encoding or "utf-8"
    sys.stdout = codecs.getwriter(enc)(sys.stdout, errors="replace")
    make_thumbnails(sorted(videos, key=unicode.lower), make_thumb)
