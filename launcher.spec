# -*- mode: python -*-

block_cipher = None
import sys
import os
import platform
sys.setrecursionlimit(5000)
sys.path.append(os.path.dirname('__file__'))

import tifffile
# import plugins
import PartSeg.__main__
import PartSegData.__init__
base_path = os.path.dirname(PartSeg.__main__.__file__)
data_path = os.path.dirname(PartSegData.__init__.__file__)

num = tifffile.__version__.split(".")[0]

if num == '0':
    hiddenimports = ["tifffile._tifffile"]
else:
    try:
        import imagecodecs
        hiddenimports = [
            "imagecodecs._aec", "imagecodecs._bitshuffle", "imagecodecs._blosc", "imagecodecs._brotli",
            "imagecodecs._bz2", "imagecodecs._gif", "imagecodecs._imcd", "imagecodecs._jpeg12", "imagecodecs._jpeg2k",
            "imagecodecs._jpeg8", "imagecodecs._jpegls", "imagecodecs._jpegsof3", "imagecodecs._jpegxl",
            "imagecodecs._jpegxr", "imagecodecs._lz4", "imagecodecs._lzf", "imagecodecs._lzma", "imagecodecs._png",
            "imagecodecs._shared", "imagecodecs._snappy", "imagecodecs._szip", "imagecodecs._template",
            "imagecodecs._tiff", "imagecodecs._webp", "imagecodecs._zfp", "imagecodecs._zlib", "imagecodecs._zopfli",
            "imagecodecs._zstd",]
    except ImportError:
        hiddenimports = ["imagecodecs_lite._imagecodecs_lite"]

if platform.system() == "Windows":
    import PyQt5
    qt_path = os.path.dirname(PyQt5.__file__)
    qt_data = [(os.path.join(qt_path, "Qt", "bin", "Qt5Core.dll"), os.path.join("PyQt5", "Qt", "bin"))]
else:
    qt_data = []

# print(["plugins." + x.name for x in plugins.get_plugins()])

a = Analysis(['launch_partseg.py'],
             # pathex=['C:\\Users\\Grzegorz\\Documents\\segmentation-gui\\PartSeg'],
             binaries=[],
             datas = [(os.path.join(data_path, x), y) for x, y in [
                 ("static_files/icons/*", "PartSegData/static_files/icons"),
                 ("static_files/initial_images/*", "PartSegData/static_files/initial_images"),
                 ("static_files/colors.npz", "PartSegData/static_files/"),
                 ("fonts/*", "PartSegData/fonts/")]] + qt_data +
                     [(os.path.join(base_path, "plugins/itk_snap_save/__init__.py"), "PartSeg/plugins/itk_snap_save")],
             hiddenimports=hiddenimports + [
                 'numpy.core._dtype_ctypes', 'sentry_sdk.integrations.logging', 'sentry_sdk.integrations.stdlib',
                 'sentry_sdk.integrations.excepthook','sentry_sdk.integrations.dedupe', 'sentry_sdk.integrations.atexit'
                 , 'sentry_sdk.integrations.modules', 'sentry_sdk.integrations.argv',
                 'sentry_sdk.integrations.threading', 'numpy.random.common', 'numpy.random.bounded_integers',
                 'numpy.random.entropy', "PartSegCore.register", "defusedxml.cElementTree"],
             # + ["plugins." + x.name for x in plugins.get_plugins()],
             hookspath=[],
             runtime_hooks=[],
             excludes=['tcl', 'Tkconstants', 'Tkinter'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='PartSeg_exec',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True)

if platform.system() == "Darwin":
    app = BUNDLE(exe,
                 a.binaries,
                 a.zipfiles,
                 a.datas,
                 name="PartSeg.app",
                 icon=os.path.join(PartSegData.__init__.icons_dir, "icon.icns"),
                 bundle_identifier=None,
                 info_plist={
                     'NSHighResolutionCapable': 'True'
                 })
else:
    coll = COLLECT(exe,
                   a.binaries,
                   a.zipfiles,
                   a.datas,
                   strip=False,
                   upx=True,
                   name='PartSeg')
