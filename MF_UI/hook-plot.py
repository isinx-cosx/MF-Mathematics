"""PyInstaller hook for plot subpackage."""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules('plot')
datas = collect_data_files('plot')
