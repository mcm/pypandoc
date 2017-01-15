# -*- coding: utf-8 -*-

import sys
import os
import shutil
import tempfile
import os.path
import subprocess
import platform

try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen


DEFAULT_TARGET_FOLDER = {
    "win32": "~\\AppData\\Local\\Pandoc",
    "linux": "~/bin",
    "darwin": "~/Applications/pandoc"
}


def _get_pandoc_urls(version=None):
    """Get the urls of pandoc's binaries
    Uses sys.platform keys, but removes the 2 from linux2
    Adding a new platform means implementing unpacking in "DownloadPandocCommand"
    and adding the URL here
    :param str version: pandoc version. e.g. "1.19.1"
    :return: str pandoc_urls: a dictionary with keys as system platform
        and values as the url pointing to respective binaries
    """
    deb_subffix = "-1"

    url_base = "https://github.com/jgm/pandoc/releases/download/" + \
        version + "/pandoc-" + version

    pandoc_urls = {
        "win32": url_base + "-windows.msi",
        "linux": url_base + deb_subffix + "-amd64.deb",
        "darwin": url_base + "-osx.pkg"
    }
    return pandoc_urls


def _make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2    # copy R bits to X
    print("* Making %s executeable..." % (path))
    os.chmod(path, mode)


def _handle_linux(filename, targetfolder):

    print("* Unpacking %s to tempfolder..." % (filename))

    tempfolder = tempfile.mkdtemp()
    cur_wd = os.getcwd()
    filename = os.path.abspath(filename)
    try:
        os.chdir(tempfolder)
        cmd = ["ar", "x", filename]
        # if only 3.5 is supported, should be `run(..., check=True)`
        subprocess.check_call(cmd)
        cmd = ["tar", "xzf", "data.tar.gz"]
        subprocess.check_call(cmd)
        # pandoc and pandoc-citeproc are in ./usr/bin subfolder
        for exe in ["pandoc", "pandoc-citeproc"]:
            src = os.path.join(tempfolder, "usr", "bin", exe)
            dst = os.path.join(targetfolder, exe)
            print("* Copying %s to %s ..." % (exe, targetfolder))
            shutil.copyfile(src, dst)
            _make_executable(dst)
        src = os.path.join(tempfolder, "usr", "share", "doc", "pandoc", "copyright")
        dst = os.path.join(targetfolder, "copyright.pandoc")
        print("* Copying copyright to %s ..." % (targetfolder))
        shutil.copyfile(src, dst)
    finally:
        os.chdir(cur_wd)
        shutil.rmtree(tempfolder)


def _handle_darwin(filename, targetfolder):
    print("* Unpacking %s to tempfolder..." % (filename))

    tempfolder = tempfile.mkdtemp()

    pkgutilfolder = os.path.join(tempfolder, 'tmp')
    cmd = ["pkgutil", "--expand", filename, pkgutilfolder]
    # if only 3.5 is supported, should be `run(..., check=True)`
    subprocess.check_call(cmd)

    # this will generate usr/local/bin below the dir
    cmd = ["tar", "xvf", os.path.join(pkgutilfolder, "pandoc.pkg", "Payload"),
           "-C", pkgutilfolder]
    subprocess.check_call(cmd)

    # pandoc and pandoc-citeproc are in the ./usr/local/bin subfolder
    for exe in ["pandoc", "pandoc-citeproc"]:
        src = os.path.join(pkgutilfolder, "usr", "local", "bin", exe)
        dst = os.path.join(targetfolder, exe)
        print("* Copying %s to %s ..." % (exe, targetfolder))
        shutil.copyfile(src, dst)
        _make_executable(dst)

    # remove temporary dir
    shutil.rmtree(tempfolder)
    print("* Done.")


def _handle_win32(filename, targetfolder):
    print("* Unpacking %s to tempfolder..." % (filename))

    tempfolder = tempfile.mkdtemp()

    cmd = ["msiexec", "/a", filename, "/qb", "TARGETDIR=%s" % (tempfolder)]
    # if only 3.5 is supported, should be `run(..., check=True)`
    subprocess.check_call(cmd)

    # pandoc.exe, pandoc-citeproc.exe, and the COPYRIGHT are in the Pandoc subfolder
    for exe in ["pandoc.exe", "pandoc-citeproc.exe", "COPYRIGHT.txt"]:
        src = os.path.join(tempfolder, "Pandoc", exe)
        dst = os.path.join(targetfolder, exe)
        print("* Copying %s to %s ..." % (exe, targetfolder))
        shutil.copyfile(src, dst)

    # remove temporary dir
    shutil.rmtree(tempfolder)
    print("* Done.")


def download_pandoc(url=None, targetfolder=None, version=None):
    """Download and unpack pandoc

    Downloads prebuild binaries for pandoc from `url` and unpacks it into
    `targetfolder`.

    :param str url: URL for the to be downloaded pandoc binary distribution for
        the platform under which this python runs. If no `url` is give, uses
        the latest available release at the time pypandoc was released.

    :param str targetfolder: directory, where the binaries should be installed
        to. If no `targetfolder` is give, uses a platform specific user
        location: `~/bin` on Linux, `~/Applications/pandoc` on Mac OS X, and
        `~\\AppData\\Local\\Pandoc` on Windows.
    """
    # get pandoc_urls
    if version is None:
        # hard-code version for now
        version = "1.19.1"
    pandoc_urls = _get_pandoc_urls(version)

    pf = sys.platform

    # compatibility with py3
    if pf.startswith("linux"):
        pf = "linux"
        if platform.architecture()[0] != "64bit":
            raise RuntimeError("Linux pandoc is only compiled for 64bit.")

    if pf not in pandoc_urls:
        raise RuntimeError("Can't handle your platform (only Linux, Mac OS X, Windows).")

    if url is None:
        url = pandoc_urls[pf]

    filename = url.split("/")[-1]
    if os.path.isfile(filename):
        print("* Using already downloaded file %s" % (filename))
    else:
        print("* Downloading pandoc from %s ..." % url)
        # https://stackoverflow.com/questions/30627937/tracebaclk-attributeerroraddinfourl-instance-has-no-attribute-exit
        response = urlopen(url)
        with open(filename, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)

    if targetfolder is None:
        targetfolder = DEFAULT_TARGET_FOLDER[pf]
    targetfolder = os.path.expanduser(targetfolder)

    # Make sure target folder exists...
    try:
        os.makedirs(targetfolder)
    except OSError:
        pass  # dir already exists...

    unpack = globals().get("_handle_" + pf)
    assert unpack is not None, "Can't handle download, only Linux, Windows and OS X are supported."

    unpack(filename, targetfolder)
