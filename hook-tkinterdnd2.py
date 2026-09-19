"""Include the TkDnD runtime in the packaged updater."""

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("tkinterdnd2")
