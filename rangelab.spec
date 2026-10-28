from pathlib import Path
import PySide6

root = Path(SPECPATH)
qt = Path(PySide6.__file__).parent
a = Analysis([str(root/'rangelab.py')], pathex=[str(root)],
    binaries=[(str(qt/name), '.') for name in ('VCRUNTIME140.dll', 'VCRUNTIME140_1.dll')],
    datas=[(str(root/'profile.json'), '.'), (str(root/'assets/rangelab.svg'), 'assets')],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['tkinter'], noarchive=False)
# Use Windows' unversioned ICU API, not another tool's incompatible ICU DLL.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() != 'icuuc.dll']
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='RangeLab', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=str(root/'assets/rangelab.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='RangeLab')
