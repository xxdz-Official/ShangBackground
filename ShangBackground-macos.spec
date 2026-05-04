# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.building.datastruct import TOC


block_cipher = None

datas = [
    ("src/qml", "qml"),
    ("src/img", "img"),
    ("img", "app_img"),
]

hiddenimports = [
    "AppKit",
    "AVFoundation",
    "CoreFoundation",
    "Foundation",
    "objc",
    "PIL._imaging",
    "PIL._imagingft",
]

excludes = [
    # Legacy Tk UI and packaging-only dependency prompts are not needed in the
    # frozen Qt Quick app. Excluding them avoids bundling Tcl/Tk.
    "_tkinter",
    "tkinter",
    "tk_main",
    "qt_main",
    "pystray",
    # The app uses system ffmpeg first for video thumbnails. If imageio is not
    # bundled, the runtime fallback simply skips it.
    "imageio",
    "imageio_ffmpeg",
    "moviepy",
    "av",
    "cv2",
    # Heavy scientific/plotting stacks accidentally pulled by imageio hooks.
    "Cython",
    "IPython",
    "jedi",
    "jinja2",
    "kiwisolver",
    "lxml",
    "markupsafe",
    "matplotlib",
    "numpy",
    "pandas",
    "scipy",
    "yaml",
    # Network/crypto stacks are optional in this app and not used by QML mode.
    "certifi",
    "charset_normalizer",
    "chardet",
    "cryptography",
    "requests",
    "urllib3",
    # Unused PySide6 modules/frameworks. The UI uses QtCore/QtGui/QtQml/
    # QtQuick/QtQuickControls2/QtQuickDialogs2 only.
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtPrintSupport",
    "PySide6.QtQuick3D",
    "PySide6.QtQuick3DAssetImport",
    "PySide6.QtQuick3DAssetUtils",
    "PySide6.QtQuick3DEffects",
    "PySide6.QtQuick3DHelpers",
    "PySide6.QtQuick3DParticles",
    "PySide6.QtQuick3DRuntimeRender",
    "PySide6.QtQuick3DSpatialAudio",
    "PySide6.QtQuick3DXr",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineQuickDelegatesQml",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtWebView",
]

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

qt_remove_patterns = [
    "/Pdf",
    "/VirtualKeyboard",
    "Qt3D",
    "QtCharts",
    "QtDataVisualization",
    "QtGraphs",
    "QtLocation",
    "QtMultimedia",
    "QtPdf",
    "QtPositioning",
    "QtQuick3D",
    "QtRemoteObjects",
    "QtScxml",
    "QtSensors",
    "QtSpatialAudio",
    "QtTextToSpeech",
    "QtVirtualKeyboard",
    "QtWebChannel",
    "QtWebEngine",
    "QtWebSockets",
    "QtWebView",
]


def keep_toc_entry(entry):
    text = "|".join(str(part) for part in entry[:2])
    return not any(pattern in text for pattern in qt_remove_patterns)


a.binaries = TOC([entry for entry in a.binaries if keep_toc_entry(entry)])
a.datas = TOC([entry for entry in a.datas if keep_toc_entry(entry)])
a.zipfiles = TOC([entry for entry in a.zipfiles if keep_toc_entry(entry)])

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ShangBackground",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ShangBackground",
)

app = BUNDLE(
    coll,
    name="ShangBackground.app",
    bundle_identifier="com.xxdz.shangbackground",
    info_plist={
        "CFBundleDisplayName": "上一个桌面背景",
        "CFBundleName": "ShangBackground",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
    },
)
