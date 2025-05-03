# constants.py
import sys
import subprocess # <--- ADD THIS IMPORT

# --- File Paths and Names ---
YAML_FILE_PATH = "devices.yaml"
LOG_FILE_PATH = "bootloader_tool_win95.log"

# --- Timeouts ---
COMMAND_TIMEOUT = 120  # Default timeout in seconds
SIDELOAD_TIMEOUT = 900 # Longer timeout for sideload (15 mins)
FLASH_TIMEOUT = 180    # Timeout for flashing (3 mins)
PUSH_PULL_TIMEOUT = 300 # Timeout for file transfers (5 mins)
SYNC_CMD_TIMEOUT = 10  # Short timeout for sync commands like 'adb devices'

# --- Platform Specific ---
# Hide console window for subprocess on Windows
# Now subprocess is imported, so this should work.
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

# --- Windows 95 Style Sheet ---
WINDOWS_95_STYLE = """
QWidget {
    background-color: #C0C0C0; /* Classic gray */
    font-family: "MS Sans Serif", Arial, sans-serif; /* Common Win95 font or fallback */
    font-size: 9pt;
}

QMainWindow, QDialog, QWidget {
    background-color: #C0C0C0;
}

QTextEdit {
    background-color: #FFFFFF; /* White background */
    color: #000000; /* Black text */
    border: 1px solid #808080; /* Gray border */
    border-top-color: #404040; /* Darker top border for inset look */
    border-left-color: #404040; /* Darker left border for inset look */
    padding: 2px;
}

QPushButton {
    background-color: #C0C0C0; /* Gray background */
    color: #000000; /* Black text */
    border-width: 1px;
    border-style: outset; /* Gives the raised button look */
    border-color: #FFFFFF #808080 #808080 #FFFFFF; /* White top/left, gray bottom/right */
    padding: 5px 10px; /* Padding inside button */
    min-height: 20px; /* Minimum height */
    min-width: 60px; /* Minimum width */
}

QPushButton:pressed {
    border-style: inset; /* Sunken look when pressed */
    border-color: #808080 #FFFFFF #FFFFFF #808080; /* Gray top/left, white bottom/right */
    background-color: #B0B0B0; /* Slightly darker gray */
}

QPushButton:disabled {
    color: #808080; /* Grayed out text */
    border-color: #C0C0C0; /* Less prominent border */
}

QPushButton:focus {
    outline: 1px dotted #000000;
    outline-offset: -3px;
}

QLabel {
    background-color: transparent; /* Labels should blend with background */
    color: #000000;
}

QStatusBar {
    background-color: #C0C0C0;
    color: #000000;
    border: 1px solid #808080;
    border-top-color: #FFFFFF;
    border-left-color: #FFFFFF;
}

QStatusBar::item {
    border: none; /* No border between status bar items */
}

QMessageBox {
    background-color: #C0C0C0;
}

QMessageBox QLabel { /* Ensure MessageBox labels follow theme */
    color: #000000;
    background-color: transparent;
}

QInputDialog {
     background-color: #C0C0C0;
}
QInputDialog QLabel, QInputDialog QLineEdit, QInputDialog QPushButton {
     color: #000000;
}
QLineEdit { /* For QInputDialog and potentially others */
    background-color: #FFFFFF;
    border: 1px solid #808080;
    border-top-color: #404040;
    border-left-color: #404040;
    color: #000000;
}

/* Add specific styles for bold mode label if needed */
QLabel#ModeLabel {
    font-weight: bold;
}
"""

# --- Logging ---
LOG_FORMAT = '%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s'

# Define logging levels using standard library names for clarity elsewhere
import logging
LOG_LEVEL_DEBUG = logging.DEBUG
LOG_LEVEL_INFO = logging.INFO
LOG_LEVEL_WARNING = logging.WARNING
LOG_LEVEL_ERROR = logging.ERROR
LOG_LEVEL_CRITICAL = logging.CRITICAL

# Output types for log messages, distinct from levels
OUTPUT_TYPE_INFO = 'info'
OUTPUT_TYPE_STDOUT = 'stdout'
OUTPUT_TYPE_STDERR = 'stderr'