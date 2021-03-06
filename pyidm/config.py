"""
    pyIDM

    multi-connections internet download manager, based on "pyCuRL/curl", "youtube_dl", and "PySimpleGUI"

    :copyright: (c) 2019-2020 by Mahmoud Elshahat.
    :license: GNU LGPLv3, see LICENSE for more details.
"""

# configurations
from queue import Queue
import os
import sys
import platform

from .version import __version__


# CONSTANTS
APP_NAME = 'pyIDM'
APP_VERSION = __version__ 
APP_TITLE = f'{APP_NAME} .. an open source download manager version {APP_VERSION}'
APP_ICON = b'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'
DEFAULT_DOWNLOAD_FOLDER = os.path.join(os.path.expanduser("~"), 'Downloads')
DEFAULT_THEME = 'reds'
DEFAULT_CONNECTIONS = 10
DEFAULT_SEGMENT_SIZE = 1048576
DEFAULT_CONCURRENT_CONNECTIONS = 3
APP_URL = 'https://github.com/pyIDM/pyIDM'
LATEST_RELEASE_URL = 'https://github.com/pyIDM/pyIDM/releases/latest'

APP_LATEST_VERSION = None  # get value from update module
ytdl_VERSION = 'xxx'  # will be loaded once youtube-dl get imported
ytdl_LATEST_VERSION = None  # get value from update module

TEST_MODE = False
FROZEN = getattr(sys, "frozen", False)  # check if app is being compiled by cx_freeze

# -------------------------------------------------------------------------------------

# current operating system  ('Windows', 'Linux', 'Darwin')
operating_system = platform.system()

# application exit flag
terminate = False 

# setting parameters
current_theme = DEFAULT_THEME
all_themes = []
speed_limit = 0  # zero == no limit
monitor_clipboard = True
show_download_window = True
max_concurrent_downloads = DEFAULT_CONCURRENT_CONNECTIONS
max_connections = DEFAULT_CONNECTIONS
segment_sie = DEFAULT_SEGMENT_SIZE
check_for_update_on_startup = True

# -------------------------------------------------------------------------------------

# folders
if hasattr(sys, 'frozen'):  # like if application froen by cx_freeze
    current_directory = os.path.dirname(sys.executable)
else:
    path = os.path.realpath(os.path.abspath(__file__))
    current_directory = os.path.dirname(path)
sys.path.insert(0, os.path.dirname(current_directory))
sys.path.insert(0, current_directory)

sett_folder = None
download_folder = DEFAULT_DOWNLOAD_FOLDER

ffmpeg_installation_folder = None 
ffmpeg_actual_path = None


# downloads
active_downloads = set()  # indexes for active downloading items
d_list = []

# queues
main_window_q = Queue()  # queue for Main application window
clipboard_q = Queue()

# -------------------------------------------------------------------------------------

# status class as an Enum
class Status:
    """used to identify status, work as an Enum"""
    downloading = 'downloading'
    paused = 'paused'
    cancelled = 'cancelled'
    completed = 'completed'
    pending = 'pending'
    merging_audio = 'merging_audio'



