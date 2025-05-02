import subprocess
import sys
import os
import yaml
import logging
import shlex # For safer command splitting
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QFileDialog, QLabel,
                             QMessageBox, QStatusBar, QProgressDialog) # Added QProgressDialog (basic)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal # Added QThread and pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QFont # Added QColor, QTextCharFormat, QFont
from qt_material import apply_stylesheet

# Import qt_material *after* PyQt5 imports
try:
    from qt_material import apply_stylesheet
    QT_MATERIAL_AVAILABLE = True
except ImportError:
    logging.warning("qt_material not found. Falling back to default style.")
    QT_MATERIAL_AVAILABLE = False


# --- Configuration ---
YAML_FILE_PATH = "devices.yaml"
LOG_FILE_PATH = "bootloader_tool.log"
COMMAND_TIMEOUT = 120  # Increased default timeout in seconds for operations like sideload

# --- Setup Logging ---
logging.basicConfig(filename=LOG_FILE_PATH, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


# --- Worker Thread for Commands ---
class WorkerThread(QThread):
    # Signals to communicate with the main thread
    started = pyqtSignal()
    finished = pyqtSignal(int, str, str) # returncode, stdout, stderr
    output = pyqtSignal(str, str) # type ('stdout' or 'stderr'), line
    error = pyqtSignal(str) # User-friendly error message

    def __init__(self, command, timeout=COMMAND_TIMEOUT):
        super().__init__()
        self.command = command
        self.timeout = timeout

    def run(self):
        self.started.emit()
        logging.info(f"Worker executing command: {self.command}")
        try:
            # Use Popen to get line-by-line output
            process = subprocess.Popen(
                shlex.split(self.command), # Safely split command into list
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8', # Use utf-8 encoding
                errors='replace' # Replace decoding errors
            )

            stdout_lines = []
            stderr_lines = []

            # Poll process and read output line by line
            while True:
                stdout_line = process.stdout.readline()
                stderr_line = process.stderr.readline()

                if stdout_line:
                    self.output.emit('stdout', stdout_line.strip())
                    stdout_lines.append(stdout_line)

                if stderr_line:
                    self.output.emit('stderr', stderr_line.strip())
                    stderr_lines.append(stderr_line)

                # Check if process has terminated and no more output is available
                if process.poll() is not None and not stdout_line and not stderr_line:
                    break

                # Add a small sleep to prevent high CPU usage
                self.msleep(10) # Sleep for 10 milliseconds


            returncode = process.wait(timeout=self.timeout) # Wait for process to finish with timeout

            full_stdout = "".join(stdout_lines).strip()
            full_stderr = "".join(stderr_lines).strip()

            self.finished.emit(returncode, full_stdout, full_stderr)

        except FileNotFoundError:
            msg = "Error: Command executable not found. Is ADB/Fastboot installed and in your system's PATH?"
            logging.error(msg, exc_info=True)
            self.error.emit(msg)
            self.finished.emit(-1, "", "") # Indicate failure
        except subprocess.TimeoutExpired:
            msg = f"Command timed out after {self.timeout} seconds."
            logging.error(f"Command '{self.command}' timed out.", exc_info=True)
            self.error.emit(msg)
            # Attempt to terminate the process if it timed out
            try:
                process.terminate()
                process.wait(timeout=5) # Give it a little time to terminate
            except:
                 pass # Ignore errors during termination attempt
            self.finished.emit(-1, "", "") # Indicate failure
        except Exception as e:
            msg = f"An unexpected error occurred: {e}"
            logging.error(f"Error during command execution: {self.command}", exc_info=True)
            self.error.emit(msg)
            self.finished.emit(-1, "", "") # Indicate failure


class BootloaderTool(QWidget):
    def __init__(self):
        super().__init__()
        self.device_config = None
        self.device_manufacturer = "Unknown"
        self.device_model = "Unknown"
        self.device_serial_adb = "N/A"
        self.device_serial_fastboot = "N/A"
        self.device_mode = 'none' # 'none', 'adb', 'fastboot', 'sideload'
        self.current_worker = None # Keep track of the active worker thread

        self.load_device_database()
        self.init_ui()
        self.start_device_state_timer()

        logging.info("Application started.")

    def load_device_database(self):
        self.device_db = {}
        # Define a robust default configuration with new command keys
        default_config = {
            'unlock_command': "fastboot oem unlock",
            'lock_command': "fastboot oem lock",
            'recovery_partition': "recovery",
            'boot_partition': "boot",
            'unlock_warning': "Unlocking the bootloader will wipe all user data (factory reset) and may void your warranty! Proceed with caution.",
            'lock_warning': "Locking the bootloader will wipe all user data. Ensure you have backups before proceeding.",
            'adb_reboot_bootloader_command': "adb reboot bootloader",
            'adb_reboot_recovery_command': "adb reboot recovery",
            'adb_reboot_system_command': "adb reboot",
            'fastboot_reboot_command': "fastboot reboot",
            'notes': 'Using default configuration. Device-specific commands may differ.'
        }

        try:
            if os.path.exists(YAML_FILE_PATH):
                with open(YAML_FILE_PATH, 'r') as f:
                    try:
                        loaded_db = yaml.safe_load(f)
                        if not isinstance(loaded_db, dict):
                            logging.error(f"Invalid YAML structure in {YAML_FILE_PATH}: Expected a dictionary.")
                            QMessageBox.warning(self, "Error", f"Invalid YAML structure in {YAML_FILE_PATH}. Using default commands only.")
                            self.device_db['default'] = default_config
                        else:
                            self.device_db = loaded_db
                            if 'default' not in self.device_db:
                                self.device_db['default'] = default_config
                                logging.warning("'default' entry not found in YAML. Using built-in default.")
                            # Ensure default config has all keys from our hardcoded default
                            for key, value in default_config.items():
                                if key not in self.device_db['default']:
                                     self.device_db['default'][key] = value
                                     logging.warning(f"Added missing default key '{key}' from built-in config.")

                            logging.info(f"Loaded device database from {YAML_FILE_PATH}")

                    except yaml.YAMLError as e:
                        logging.error(f"Error parsing YAML file {YAML_FILE_PATH}: {e}", exc_info=True)
                        QMessageBox.warning(self, "Error", f"Could not parse {YAML_FILE_PATH}.\n{e}\nUsing default commands only.")
                        self.device_db['default'] = default_config
                    except Exception as e:
                        logging.error(f"Unexpected error loading {YAML_FILE_PATH}: {e}", exc_info=True)
                        QMessageBox.warning(self, "Error", f"Unexpected error loading {YAML_FILE_PATH}.\n{e}\nUsing default commands only.")
                        self.device_db['default'] = default_config

                if not self.device_db and os.path.exists(YAML_FILE_PATH):
                     logging.warning(f"{YAML_FILE_PATH} is empty or invalid. Using default commands only.")
                     self.device_db['default'] = default_config

            else:
                logging.warning(f"{YAML_FILE_PATH} not found. Using default commands only.")
                self.device_db['default'] = default_config

        except Exception as e:
            logging.critical(f"Critical error during database loading: {e}", exc_info=True)
            QMessageBox.critical(self, "Critical Error", f"A critical error occurred while loading the device database.\n{e}\nThe application may not function correctly.")
            if 'default' not in self.device_db:
                 self.device_db['default'] = default_config

        # Always start with default config until a device is detected
        self.device_config = self.device_db.get('default')


    def init_ui(self):
        self.setWindowTitle("Enhanced Android Bootloader & Recovery Tool")
        self.setGeometry(100, 100, 900, 700) # Make window a bit larger

        layout = QVBoxLayout()

        # --- Device Info Area ---
        self.info_layout = QHBoxLayout()
        self.manufacturer_label = QLabel("Manufacturer: Unknown")
        self.model_label = QLabel("Model: Unknown")
        self.serial_label = QLabel("Serial: N/A")
        self.mode_label = QLabel("Mode: Disconnected")

        font = QFont()
        font.setBold(True)
        self.mode_label.setFont(font)

        self.info_layout.addWidget(self.manufacturer_label)
        self.info_layout.addWidget(self.model_label)
        self.info_layout.addWidget(self.serial_label)
        self.info_layout.addStretch(1) # Push labels to the left
        self.info_layout.addWidget(self.mode_label)
        layout.addLayout(self.info_layout)

        # --- Output Area ---
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Command output and logs will appear here...")
        # Improve default text color for dark themes
        if QT_MATERIAL_AVAILABLE:
             self.output.setStyleSheet("QTextEdit { color: #ABB2BF; }") # A common code-friendly color

        layout.addWidget(self.output)

        # --- Control Buttons ---
        self.button_layout_main = QHBoxLayout()

        self.detect_button = QPushButton("Detect Device Details")
        self.detect_button.setToolTip("Detect device manufacturer, model, and serial number (ADB or Fastboot)")
        self.detect_button.clicked.connect(self.detect_device_details)
        self.button_layout_main.addWidget(self.detect_button)

        self.unlock_button = QPushButton("Unlock Bootloader")
        self.unlock_button.setToolTip("Attempt to unlock the bootloader (Requires device in Fastboot mode). Wipes data!")
        self.unlock_button.clicked.connect(self.unlock_bootloader)
        self.button_layout_main.addWidget(self.unlock_button)

        self.lock_button = QPushButton("Lock Bootloader")
        self.lock_button.setToolTip("Lock the bootloader (Requires device in Fastboot mode). Wipes data!")
        self.lock_button.clicked.connect(self.lock_bootloader)
        self.button_layout_main.addWidget(self.lock_button)

        self.recovery_button = QPushButton("Flash Recovery")
        self.recovery_button.setToolTip("Flash a custom recovery image (Requires device in Fastboot mode)")
        self.recovery_button.clicked.connect(self.flash_recovery)
        self.button_layout_main.addWidget(self.recovery_button)

        self.magisk_button = QPushButton("Flash Patched Boot")
        self.magisk_button.setToolTip("Flash a boot image previously patched by Magisk (Requires device in Fastboot mode)")
        self.magisk_button.clicked.connect(self.flash_patched_boot)
        self.button_layout_main.addWidget(self.magisk_button)

        layout.addLayout(self.button_layout_main)

        # --- Reboot Buttons ---
        self.button_layout_reboot = QHBoxLayout()

        self.reboot_system_button = QPushButton("Reboot System")
        self.reboot_system_button.setToolTip("Reboot device to normal system (ADB or Fastboot)")
        self.reboot_system_button.clicked.connect(self.reboot_system)
        self.button_layout_reboot.addWidget(self.reboot_system_button)

        self.reboot_recovery_button = QPushButton("Reboot Recovery")
        self.reboot_recovery_button.setToolTip("Reboot device to recovery mode (ADB)")
        self.reboot_recovery_button.clicked.connect(self.reboot_recovery)
        self.button_layout_reboot.addWidget(self.reboot_recovery_button)

        self.reboot_bootloader_button = QPushButton("Reboot Bootloader")
        self.reboot_bootloader_button.setToolTip("Reboot device to bootloader/fastboot mode (ADB)")
        self.reboot_bootloader_button.clicked.connect(self.reboot_bootloader)
        self.button_layout_reboot.addWidget(self.reboot_bootloader_button)

        layout.addLayout(self.button_layout_reboot)


        # --- Sideload / File Operations ---
        self.button_layout_file = QHBoxLayout()

        self.sideload_button = QPushButton("ADB Sideload ZIP")
        self.sideload_button.setToolTip("Flash a ROM or ZIP file via ADB Sideload (Requires device in Recovery mode with Sideload active)")
        self.sideload_button.clicked.connect(self.flash_rom_sideload)
        self.button_layout_file.addWidget(self.sideload_button)

        # Add placeholder buttons for future file ops
        self.adb_push_button = QPushButton("ADB Push File")
        self.adb_push_button.setToolTip("Push a file to the device (Requires device in ADB mode)")
        self.adb_push_button.clicked.connect(self.adb_push_file)
        self.adb_push_button.setEnabled(False) # Disable initially
        self.button_layout_file.addWidget(self.adb_push_button)

        self.adb_pull_button = QPushButton("ADB Pull File")
        self.adb_pull_button.setToolTip("Pull a file from the device (Requires device in ADB mode)")
        self.adb_pull_button.clicked.connect(self.adb_pull_file)
        self.adb_pull_button.setEnabled(False) # Disable initially
        self.button_layout_file.addWidget(self.adb_pull_button)

        layout.addLayout(self.button_layout_file)


        # --- Status Bar ---
        self.statusBar = QStatusBar()
        self.statusBar.showMessage("Initializing. Ensure ADB/Fastboot drivers are installed.")
        layout.addWidget(self.statusBar)

        self.setLayout(layout)

        # Initial button state update
        self.update_button_states('none')


    def start_device_state_timer(self):
        """Starts a timer to periodically check device state."""
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self.check_device_state)
        self.state_timer.start(3000) # Check every 3 seconds


    def check_device_state(self):
        """Checks if an ADB or Fastboot device is connected and updates UI/buttons."""
        if self.current_worker is not None and self.current_worker.isRunning():
             # Don't check state if a command is currently running
             return

        adb_output, adb_success = self.run_command_sync("adb devices")
        fastboot_output, fastboot_success = self.run_command_sync("fastboot devices")

        new_mode = 'none'
        serial_adb = "N/A"
        serial_fastboot = "N/A"

        # Check for ADB devices (usually ends with 'device' or 'sideload')
        adb_lines = adb_output.splitlines()
        if adb_success and len(adb_lines) > 1:
             # Look for lines with 'device' or 'sideload' status
            for line in adb_lines[1:]: # Skip "List of devices attached"
                 parts = line.split('\t')
                 if len(parts) == 2:
                     serial, status = parts
                     if status in ('device', 'sideload'):
                         new_mode = 'adb' if status == 'device' else 'sideload'
                         serial_adb = serial # Assume first found device for now
                         break # Found an ADB device

        # Check for Fastboot devices (usually ends with 'fastboot')
        fastboot_lines = fastboot_output.splitlines()
        if fastboot_success and len(fastboot_lines) > 0:
            # Fastboot output might just be the serial number followed by fastboot
            for line in fastboot_lines:
                 parts = line.split('\t')
                 if len(parts) == 2 and parts[1].strip() == 'fastboot':
                     new_mode = 'fastboot'
                     serial_fastboot = parts[0].strip() # Assume first found device
                     break # Found a Fastboot device


        # Update mode and serials
        self.device_mode = new_mode
        self.device_serial_adb = serial_adb
        self.device_serial_fastboot = serial_fastboot

        # Update labels
        self.serial_label.setText(f"Serial: {serial_adb if new_mode in ('adb', 'sideload') else serial_fastboot if new_mode == 'fastboot' else 'N/A'}")
        self.mode_label.setText(f"Mode: {new_mode.capitalize()}")

        # Update button states based on the new mode
        self.update_button_states(new_mode)

        # If a device is connected and details are unknown, try detecting
        if new_mode != 'none' and self.manufacturer_label.text() == "Manufacturer: Unknown":
             # Delay detection slightly to avoid interfering with mode change
             QTimer.singleShot(500, self.detect_device_details)


    def update_button_states(self, mode):
        """Enables/disables buttons based on the current device mode."""
        is_adb = mode in ('adb', 'sideload')
        is_fastboot = mode == 'fastboot'
        is_sideload = mode == 'sideload'

        # Main Control Buttons (mostly Fastboot)
        self.unlock_button.setEnabled(is_fastboot)
        self.lock_button.setEnabled(is_fastboot)
        self.recovery_button.setEnabled(is_fastboot)
        self.magisk_button.setEnabled(is_fastboot)

        # Reboot Buttons
        # Reboot System works from both ADB and Fastboot
        self.reboot_system_button.setEnabled(is_adb or is_fastboot)
        # Reboot Recovery/Bootloader work from ADB
        self.reboot_recovery_button.setEnabled(is_adb)
        self.reboot_bootloader_button.setEnabled(is_adb)


        # Sideload / File Operations
        self.sideload_button.setEnabled(is_sideload) # Sideload specifically needs sideload mode
        self.adb_push_button.setEnabled(is_adb) # Push/Pull need normal ADB mode
        self.adb_pull_button.setEnabled(is_adb)


        # Detect button is always enabled as it's the entry point
        self.detect_button.setEnabled(True)

        # If any worker is running, disable all action buttons
        if self.current_worker is not None and self.current_worker.isRunning():
            for button in self.findChildren(QPushButton):
                if button != self.detect_button: # Keep detect enabled? Or disable all? Let's disable all actions.
                   button.setEnabled(False)


    def log_and_append(self, message, level=logging.INFO, status_msg=None, output_type='info'):
        """Helper to log message and append to GUI output with color."""
        # Use QTimer.singleShot to ensure GUI update happens on the main thread
        QTimer.singleShot(0, lambda: self._append_to_output(message, level, status_msg, output_type))

    def _append_to_output(self, message, level, status_msg, output_type):
        """Internal method to safely append to QTextEdit with formatting."""
        format = QTextCharFormat()
        prefix = ""

        if level == logging.ERROR:
            logging.error(message)
            format.setForeground(QColor('red'))
            prefix = "[ERROR] "
        elif level == logging.WARNING:
            logging.warning(message)
            format.setForeground(QColor('orange'))
            prefix = "[WARNING] "
        elif level == logging.CRITICAL:
             logging.critical(message)
             format.setForeground(QColor('darkred'))
             prefix = "[CRITICAL] "
        else: # INFO or DEBUG (if enabled)
            logging.info(message)
            format.setForeground(QColor(self.palette().color(QColor.Text))) # Use default text color
            prefix = "[*] "

        # Add specific formatting for stdout/stderr if needed
        if output_type == 'stdout':
            format.setForeground(QColor('lightblue')) # Or green, or grey
            prefix = "[STDOUT] "
        elif output_type == 'stderr':
             format.setForeground(QColor('yellow')) # Or orange, or grey
             prefix = "[STDERR] "


        cursor = self.output.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(prefix + message + '\n', format)
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())  # Auto-scroll

        if status_msg:
            QTimer.singleShot(0, lambda: self.statusBar.showMessage(status_msg, 5000))


    def run_command_async(self, command, success_msg=None, error_msg_prefix=None, timeout=COMMAND_TIMEOUT):
        """Starts a command in a worker thread."""
        if self.current_worker is not None and self.current_worker.isRunning():
            self.log_and_append("Another command is already running. Please wait.", level=logging.WARNING, status_msg="Busy with another command.")
            return False # Indicate command was not started

        self.log_and_append(f"Preparing command: {command}", status_msg=f"Preparing: {command.split(' ')[0]}...")
        self.current_worker = WorkerThread(command, timeout)

        # Connect signals
        self.current_worker.started.connect(self._command_started)
        self.current_worker.output.connect(self._command_output)
        self.current_worker.error.connect(self._command_error)
        self.current_worker.finished.connect(self._command_finished)

        # Start the worker thread
        self.current_worker.start()
        return True # Indicate command was started

    def run_command_sync(self, command, timeout=COMMAND_TIMEOUT):
        """Runs a command synchronously (blocking). Use ONLY for quick checks like 'adb devices'."""
        # Be cautious using this for anything potentially slow.
        try:
            process = subprocess.run(
                 shlex.split(command),
                 capture_output=True,
                 text=True,
                 encoding='utf-8',
                 errors='replace',
                 timeout=timeout
             )
            return process.stdout.strip(), process.returncode == 0
        except Exception:
             # Don't log synchronous check errors unless critical
             return "", False


    def _command_started(self):
        """Slot for when a command worker starts."""
        self.log_and_append(f"Command worker started.", status_msg="Command running...")
        self.update_button_states(self.device_mode) # Update states to disable buttons


    def _command_output(self, output_type, line):
        """Slot for receiving output from a command worker."""
        # Append output line by line as it comes
        self.log_and_append(line, level=logging.INFO, output_type=output_type)


    def _command_error(self, message):
        """Slot for receiving user-friendly error messages from a worker."""
        self.log_and_append(message, level=logging.ERROR, status_msg="Command error!")


    def _command_finished(self, returncode, stdout, stderr):
        """Slot for when a command worker finishes."""
        command = self.current_worker.command # Get command from the finished worker
        self.current_worker = None # Clear the worker reference

        if returncode == 0:
            self.log_and_append(f"Command finished successfully: {command}", status_msg="Command finished.")
            # Specific success messages could go here based on the command
            if "fastboot oem unlock" in command or "fastboot flashing unlock" in command:
                 self.log_and_append("Unlock command sent. Check device screen for confirmation!", level=logging.WARNING)
            elif "fastboot oem lock" in command or "fastboot flashing lock" in command:
                 self.log_and_append("Lock command sent. Check device screen for confirmation!", level=logging.WARNING)
            elif "adb sideload" in command:
                 self.log_and_append("Sideload command sent. Check device and output above for progress.", status_msg="Sideload started.")

        else:
            # _command_error might have already logged a message
            # If returncode != 0 but no specific error was emitted, log a generic one
            if not stderr and not stdout: # Handle cases with no output on failure
                 self.log_and_append(f"Command failed with return code {returncode}: {command}", level=logging.ERROR, status_msg="Command failed.")
            else:
                 # Output was already logged line by line by _command_output
                 self.log_and_append(f"Command failed with return code {returncode}. See output above.", level=logging.ERROR, status_msg="Command failed.")


        self.update_button_states(self.device_mode) # Re-enable/update buttons


    def get_device_property_adb(self, prop_name):
        """Gets an Android property using adb shell getprop (async wrapper)."""
        # Note: This *starts* the command, the result comes via signals
        command = f"adb shell getprop {prop_name}"
        self.run_command_async(command) # Need to handle result in a signal slot if used this way


    def get_fastboot_variables(self):
        """Gets all fastboot variables using 'fastboot getvar all' (async wrapper)."""
         # Note: This *starts* the command, the result comes via signals
        command = "fastboot getvar all"
        self.run_command_async(command) # Need to handle result in a signal slot


    def detect_device_details(self):
        """Detects manufacturer and model using ADB and Fastboot."""
        self.log_and_append("Attempting to detect device details...", status_msg="Detecting device...")

        try:
            # First, try ADB properties if in ADB mode
            if self.device_mode in ('adb', 'sideload'):
                # Get properties directly via sync for detection logic
                manufacturer_output, manufacturer_success = self.run_command_sync("adb shell getprop ro.product.manufacturer")
                model_output, model_success = self.run_command_sync("adb shell getprop ro.product.model")

                manufacturer = manufacturer_output if manufacturer_success else None
                model = model_output if model_success else None
                serial = self.device_serial_adb

                if manufacturer and model:
                    self.device_manufacturer = manufacturer.strip()
                    self.device_model = model.strip()
                    self.manufacturer_label.setText(f"Manufacturer: {self.device_manufacturer}")
                    self.model_label.setText(f"Model: {self.device_model}")
                    self.serial_label.setText(f"Serial: {serial}")
                    self.device_config = self.find_device_config(self.device_manufacturer, self.device_model)
                    self.log_and_append(f"Detected device: {self.device_manufacturer} {self.device_model} (Serial: {serial}) via ADB", status_msg=f"Detected: {self.device_manufacturer} {self.device_model}")
                    config_source = "YAML" if self.device_config != self.device_db.get('default') else "Default"
                    self.log_and_append(f"Using device configuration: {config_source}")
                    if self.device_config and 'notes' in self.device_config:
                        self.log_and_append(f"Device Notes: {self.device_config['notes']}", level=logging.WARNING)
                    self.statusBar.showMessage(f"Detected: {self.device_manufacturer} {self.device_model}", 5000)
                    # If ADB detection successful, also try getting all properties via async
                    self.run_command_async("adb shell getprop", success_msg="Fetched ADB properties.", error_msg_prefix="Failed to fetch all ADB properties.")

                elif manufacturer:
                     self.device_manufacturer = manufacturer.strip()
                     self.device_model = "Unknown"
                     self.manufacturer_label.setText(f"Manufacturer: {self.device_manufacturer}")
                     self.model_label.setText("Model: Unknown")
                     self.serial_label.setText(f"Serial: {serial}")
                     self.device_config = self.find_device_config(self.device_manufacturer, None)
                     self.log_and_append(f"Detected Manufacturer: {self.device_manufacturer} (Serial: {serial}) but could not get model. Attempting manufacturer match or using default configuration.", level=logging.WARNING)
                     config_source = "YAML (Manufacturer Match)" if self.device_config and self.device_config != self.device_db.get('default') else "Default"
                     self.log_and_append(f"Using configuration: {config_source}")
                     if self.device_config and 'notes' in self.device_config:
                        self.log_and_append(f"Device Notes: {self.device_config['notes']}", level=logging.WARNING)
                     self.statusBar.showMessage("Detected Manufacturer, but failed to get Model.", 5000)
                     self.run_command_async("adb shell getprop", success_msg="Fetched ADB properties.", error_msg_prefix="Failed to fetch all ADB properties.")
                else:
                     self.log_and_append("Failed to get ADB device properties.", level=logging.WARNING)
                     # Fall through to Fastboot check


            # If not in ADB mode or ADB detection failed, try Fastboot
            if self.device_mode == 'fastboot':
                 serial = self.device_serial_fastboot
                 self.serial_label.setText(f"Serial: {serial}")
                 self.log_and_append(f"Device detected in Fastboot mode (Serial: {serial}). Getting fastboot variables...", status_msg="Detecting via Fastboot...")

                 # Get fastboot variables using async
                 self.get_fastboot_variables() # Output handled by signal slot

                 # Fastboot doesn't provide manufacturer/model standard properties easily
                 self.manufacturer_label.setText("Manufacturer: Unknown (Fastboot)")
                 self.model_label.setText("Model: Unknown (Fastboot)")
                 self.device_manufacturer = "Unknown"
                 self.device_model = "Unknown"
                 # Use default config in Fastboot unless a specific 'fastboot getvar all' parsing reveals manufacturer/model
                 self.device_config = self.device_db.get('default')
                 self.log_and_append("Using default configuration (Fastboot mode often has less detailed built-in properties).", level=logging.WARNING)
                 if self.device_config and 'notes' in self.device_config:
                        self.log_and_append(f"Device Notes: {self.device_config['notes']}", level=logging.WARNING)
                 self.statusBar.showMessage(f"Fastboot device detected (Serial: {serial}).", 5000)


            if self.device_mode == 'none':
                 self.manufacturer_label.setText("Manufacturer: Unknown")
                 self.model_label.setText("Model: Unknown")
                 self.serial_label.setText("Serial: N/A")
                 self.device_config = self.device_db.get('default')
                 self.log_and_append("No device detected in ADB or Fastboot mode.", level=logging.WARNING, status_msg="No device detected.")

        except Exception as e:
            self.log_and_append(f"An error occurred during device detection: {e}", level=logging.ERROR)
            self.statusBar.showMessage("Error detecting device details. Check logs.", 5000)
            self.device_config = self.device_db.get('default')  # Ensure config is at least default on error
            self.manufacturer_label.setText("Manufacturer: Unknown (Error)")
            self.model_label.setText("Model: Unknown (Error)")
            self.serial_label.setText("Serial: N/A")


    def find_device_config(self, manufacturer, model):
        """Finds the device configuration based on manufacturer and model."""
        if not self.device_db:
            logging.warning("Device database is empty.")
            return self.device_db.get('default')

        # Prioritize exact match (manufacturer + model)
        if manufacturer and model:
            exact_key = f"{manufacturer.lower()} {model.lower()}"
            if exact_key in self.device_db:
                logging.info(f"Found exact match in config for '{exact_key}'")
                return self.device_db[exact_key]

        # Fallback to manufacturer match if model is unknown or exact match not found
        if manufacturer:
             manufacturer_key = manufacturer.lower()
             if manufacturer_key in self.device_db:
                 logging.info(f"Found manufacturer match in config for '{manufacturer_key}'")
                 return self.device_db[manufacturer_key]

        logging.warning(f"No specific config found for Manufacturer='{manufacturer}', Model='{model}'. Using default.")
        return self.device_db.get('default')


    # --- Core Operations (using async commands) ---

    def unlock_bootloader(self):
        """Handles the bootloader unlock process with warnings."""
        if self.device_mode != 'fastboot':
            QMessageBox.warning(self, "Wrong Mode", "Unlock requires the device to be in Fastboot mode.")
            self.log_and_append("Unlock failed: Device not in Fastboot mode.", level=logging.ERROR)
            return

        config = self.device_config or self.device_db.get('default')
        unlock_command_template = config.get('unlock_command', 'fastboot oem unlock')
        warning_message = config.get('unlock_warning', "Unlocking the bootloader will erase all data on the device. Ensure you have backups before proceeding.")

        reply = QMessageBox.warning(self, "Unlock Bootloader - WARNING",
                                    f"{warning_message}\n\nTHIS ACTION CANNOT BE UNDONE AND WILL ERASE YOUR PHONE.\n\nDo you want to proceed?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.log_and_append("Bootloader unlock cancelled by user.", status_msg="Unlock cancelled.")
            return

        self.log_and_append("User confirmed unlock warning.", level=logging.WARNING)

        # Format command template if needed (basic example)
        unlock_command = unlock_command_template.format(
             manufacturer=self.device_manufacturer,
             model=self.device_model,
             serial=self.device_serial_fastboot
        )

        self.run_command_async(unlock_command, success_msg="Unlock command sent.", error_msg_prefix="Failed to send unlock command")


    def lock_bootloader(self):
        """Handles the bootloader lock process with warnings."""
        if self.device_mode != 'fastboot':
            QMessageBox.warning(self, "Wrong Mode", "Lock requires the device to be in Fastboot mode.")
            self.log_and_append("Lock failed: Device not in Fastboot mode.", level=logging.ERROR)
            return

        config = self.device_config or self.device_db.get('default')
        lock_command_template = config.get('lock_command', 'fastboot oem lock')
        warning_message = config.get('lock_warning', "Locking the bootloader will erase all data on the device. Ensure you have backups before proceeding.")

        reply = QMessageBox.warning(self, "Lock Bootloader - WARNING",
                                    f"{warning_message}\n\nTHIS ACTION CANNOT BE UNDONE AND WILL ERASE YOUR PHONE.\n\nDo you want to proceed?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.log_and_append("Bootloader lock cancelled by user.", status_msg="Lock cancelled.")
            return

        self.log_and_append("User confirmed lock warning.", level=logging.WARNING)

        # Format command template
        lock_command = lock_command_template.format(
             manufacturer=self.device_manufacturer,
             model=self.device_model,
             serial=self.device_serial_fastboot
        )

        self.run_command_async(lock_command, success_msg="Lock command sent.", error_msg_prefix="Failed to send lock command")


    def flash_recovery(self):
        """Handles flashing a recovery image."""
        if self.device_mode != 'fastboot':
            QMessageBox.warning(self, "Wrong Mode", "Flashing recovery requires the device to be in Fastboot mode.")
            self.log_and_append("Flash failed: Device not in Fastboot mode.", level=logging.ERROR)
            return

        config = self.device_config or self.device_db.get('default')
        recovery_partition = config.get('recovery_partition', 'recovery')

        file_path, _ = QFileDialog.getOpenFileName(self, f"Select Recovery Image (.img) for '{recovery_partition}'", "", "Image Files (*.img);;All Files (*)")
        if not file_path:
            self.log_and_append("File selection cancelled.", status_msg="Flash cancelled.")
            return

        self.log_and_append(f"Selected file: {file_path}", status_msg="File selected.")

        reply = QMessageBox.question(self, "Confirm Flash Recovery",
                                     f"Are you sure you want to flash '{os.path.basename(file_path)}' to the '{recovery_partition}' partition?\n\n"
                                     "WARNING: Flashing an incorrect image can brick your device!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.log_and_append("Recovery flash cancelled by user.", status_msg="Flash cancelled.")
            return

        self.log_and_append("User confirmed recovery flash.", level=logging.WARNING)

        command = f"fastboot flash {recovery_partition} \"{file_path}\""
        self.run_command_async(command, success_msg="Recovery flash command sent.", error_msg_prefix="Failed to send flash command")


    def flash_patched_boot(self):
        """Handles flashing a patched boot image (e.g., for Magisk)."""
        if self.device_mode != 'fastboot':
            QMessageBox.warning(self, "Wrong Mode", "Flashing boot requires the device to be in Fastboot mode.")
            self.log_and_append("Flash failed: Device not in Fastboot mode.", level=logging.ERROR)
            return

        config = self.device_config or self.device_db.get('default')
        boot_partition = config.get('boot_partition', 'boot')

        file_path, _ = QFileDialog.getOpenFileName(self, f"Select Patched Boot Image (.img) for '{boot_partition}'", "", "Image Files (*.img);;All Files (*)")
        if not file_path:
            self.log_and_append("File selection cancelled.", status_msg="Flash cancelled.")
            return

        self.log_and_append(f"Selected file: {file_path}", status_msg="File selected.")

        reply = QMessageBox.question(self, "Confirm Flash Patched Boot",
                                     f"Are you sure you want to flash '{os.path.basename(file_path)}' to the '{boot_partition}' partition?\n\n"
                                     "WARNING: Flashing an incorrect or unpatched boot image can cause boot loops!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.log_and_append("Patched boot flash cancelled by user.", status_msg="Flash cancelled.")
            return

        self.log_and_append("User confirmed patched boot flash.", level=logging.WARNING)

        command = f"fastboot flash {boot_partition} \"{file_path}\""
        self.run_command_async(command, success_msg="Patched boot flash command sent.", error_msg_prefix="Failed to send flash command")


    def flash_rom_sideload(self):
        """Handles flashing a ROM/ZIP via ADB Sideload."""
        if self.device_mode != 'sideload':
            QMessageBox.warning(self, "Wrong Mode", "ADB Sideload requires the device to be in recovery mode with Sideload active.")
            self.log_and_append("Sideload failed: Device not in Sideload mode.", level=logging.ERROR)
            return

        QMessageBox.information(self, "ADB Sideload Instructions",
                                "Ensure your device is in recovery mode and ADB Sideload is enabled!\n"
                                "This tool will now prompt you to select the ZIP file to sideload.\n\n"
                                "Click OK when your device is ready.", QMessageBox.Ok)

        file_path, _ = QFileDialog.getOpenFileName(self, "Select ROM/ZIP File (.zip)", "", "ZIP Files (*.zip);;All Files (*)")
        if not file_path:
            self.log_and_append("File selection cancelled.", status_msg="Sideload cancelled.")
            return

        self.log_and_append(f"Selected file: {file_path}", status_msg="File selected.")

        reply = QMessageBox.question(self, "Confirm ADB Sideload",
                                     f"Are you sure you want to sideload '{os.path.basename(file_path)}'?\n\n"
                                     "Ensure your device is in ADB Sideload mode!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.log_and_append("ADB Sideload cancelled by user.", status_msg="Sideload cancelled.")
            return

        self.log_and_append("User confirmed ADB Sideload.", level=logging.WARNING)

        command = f"adb sideload \"{file_path}\""
        # Sideload can take a long time, use a larger timeout or rely on process termination
        self.run_command_async(command, success_msg="ADB Sideload command sent.", error_msg_prefix="Failed to send sideload command", timeout=600) # 10 minutes timeout


    # --- Reboot Operations ---
    def reboot_system(self):
        """Reboots the device to the system."""
        if self.device_mode == 'adb':
             command = self.device_config.get('adb_reboot_system_command', 'adb reboot')
        elif self.device_mode == 'fastboot':
             command = self.device_config.get('fastboot_reboot_command', 'fastboot reboot')
        else:
             QMessageBox.warning(self, "Wrong Mode", "Reboot System works from ADB or Fastboot mode.")
             self.log_and_append("Reboot System failed: Device not in ADB or Fastboot mode.", level=logging.ERROR)
             return

        self.run_command_async(command, success_msg="Reboot System command sent.", error_msg_prefix="Failed to send Reboot System command")

    def reboot_recovery(self):
        """Reboots the device to recovery mode."""
        if self.device_mode != 'adb':
            QMessageBox.warning(self, "Wrong Mode", "Reboot Recovery requires the device to be in ADB mode.")
            self.log_and_append("Reboot Recovery failed: Device not in ADB mode.", level=logging.ERROR)
            return
        command = self.device_config.get('adb_reboot_recovery_command', 'adb reboot recovery')
        self.run_command_async(command, success_msg="Reboot Recovery command sent.", error_msg_prefix="Failed to send Reboot Recovery command")

    def reboot_bootloader(self):
        """Reboots the device to bootloader/fastboot mode."""
        if self.device_mode != 'adb':
            QMessageBox.warning(self, "Wrong Mode", "Reboot Bootloader requires the device to be in ADB mode.")
            self.log_and_append("Reboot Bootloader failed: Device not in ADB mode.", level=logging.ERROR)
            return
        command = self.device_config.get('adb_reboot_bootloader_command', 'adb reboot bootloader')
        self.run_command_async(command, success_msg="Reboot Bootloader command sent.", error_msg_prefix="Failed to send Reboot Bootloader command")


    # --- Placeholder File Operations ---
    def adb_push_file(self):
         QMessageBox.information(self, "Feature Not Implemented", "ADB Push File feature is not yet implemented.")
         self.log_and_append("ADB Push File clicked - Feature not implemented.", level=logging.INFO)

    def adb_pull_file(self):
         QMessageBox.information(self, "Feature Not Implemented", "ADB Pull File feature is not yet implemented.")
         self.log_and_append("ADB Pull File clicked - Feature not implemented.", level=logging.INFO)


    # --- Clean up ---
    def closeEvent(self, event):
        """Handle application closing."""
        if self.current_worker is not None and self.current_worker.isRunning():
            reply = QMessageBox.question(self, "Close Application",
                                         "A command is currently running. Closing the application will terminate it.\nDo you want to close?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                 self.current_worker.terminate() # Attempt to terminate the thread
                 self.current_worker.wait(2000) # Wait up to 2 seconds for it to finish
                 logging.info("Application closed.")
                 event.accept()
            else:
                event.ignore()
        else:
            logging.info("Application closed.")
            event.accept()


if __name__ == "__main__":
    # It's generally best to create the QApplication instance first
    app = QApplication(sys.argv)

    # Apply Material Design theme *after* QApplication is created
    if QT_MATERIAL_AVAILABLE:
        try:
            apply_stylesheet(app, theme='dark_teal.xml')  # You can choose other themes
        except Exception as e:
            logging.warning(f"Could not apply qt_material stylesheet: {e}")
            print(f"Warning: Could not apply qt_material stylesheet: {e}")
            print("Ensure 'qt_material' is installed and theme file exists.")
            # Continue without stylesheet if it fails


    window = BootloaderTool()
    window.show()
    sys.exit(app.exec_())