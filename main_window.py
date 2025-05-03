# main_window.py
import sys
import os
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
                             QFileDialog, QLabel, QMessageBox, QStatusBar, QInputDialog,
                             QSizePolicy)
from PyQt5.QtCore import pyqtSlot, QTimer, Qt
from PyQt5.QtGui import QFont # Keep import in case needed later

# Import from other application modules
from device_manager import DeviceManager
from config_manager import ConfigManager
from constants import (LOG_LEVEL_INFO, LOG_LEVEL_WARNING, LOG_LEVEL_ERROR, LOG_LEVEL_CRITICAL,
                       LOG_LEVEL_DEBUG, # Added for potential debug logs
                       OUTPUT_TYPE_INFO, OUTPUT_TYPE_STDERR, OUTPUT_TYPE_STDOUT)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        logging.info("MainWindow.__init__ started")
        # Order matters: Config needed by Manager
        self.config_manager = ConfigManager()
        self.device_manager = DeviceManager(self.config_manager)

        self.init_ui()
        self.connect_signals()

        # Start device monitoring via the manager after UI is set up
        self.device_manager.start_monitoring()
        logging.info("MainWindow.__init__ finished.")

    def init_ui(self):
        """Initializes all UI elements and layouts."""
        logging.debug("MainWindow.init_ui started.")
        self.setWindowTitle("Android Bootloader Tool+ (Win95 Style)")
        self.setGeometry(100, 100, 800, 600) # x, y, width, height

        main_layout = QVBoxLayout(self) # Set layout directly on the QWidget

        # --- Device Info Area ---
        info_layout = QHBoxLayout()
        self.manufacturer_label = QLabel("Manufacturer: Unknown")
        self.model_label = QLabel("Model: Unknown")
        self.serial_label = QLabel("Serial: N/A")
        self.mode_label = QLabel("Mode: Disconnected")
        self.mode_label.setObjectName("ModeLabel") # For specific styling

        # Set size policies to prevent labels stretching too much
        self.manufacturer_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.model_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.serial_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

        info_layout.addWidget(self.manufacturer_label)
        info_layout.addWidget(self.model_label)
        info_layout.addWidget(self.serial_label)
        info_layout.addStretch(1) # Push mode label to the right
        info_layout.addWidget(self.mode_label)
        main_layout.addLayout(info_layout)

        # --- Output Area ---
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("Command output and status messages appear here...")
        # Optional: Set a monospaced font if desired
        # self.output_text.setFont(QFont("Monospace", 9))
        main_layout.addWidget(self.output_text)

        # --- Button Layouts ---
        button_grid = [QHBoxLayout() for _ in range(3)] # 3 rows

        # Row 1: Core Actions
        self.detect_button = QPushButton("Detect Device")
        self.detect_button.setToolTip("Detect device details (ADB or Fastboot)")
        button_grid[0].addWidget(self.detect_button)

        self.unlock_button = QPushButton("Unlock Bootloader")
        self.unlock_button.setToolTip("Unlock bootloader (Fastboot mode). Wipes data!")
        button_grid[0].addWidget(self.unlock_button)

        self.lock_button = QPushButton("Lock Bootloader")
        self.lock_button.setToolTip("Lock bootloader (Fastboot mode). Might wipe data!")
        button_grid[0].addWidget(self.lock_button)

        # Row 2: Flashing & Booting
        self.recovery_button = QPushButton("Flash Recovery")
        self.recovery_button.setToolTip("Flash recovery.img (Fastboot mode)")
        button_grid[1].addWidget(self.recovery_button)

        self.boot_button = QPushButton("Flash Boot")
        self.boot_button.setToolTip("Flash boot.img (Fastboot mode)")
        button_grid[1].addWidget(self.boot_button)

        self.boot_no_flash_button = QPushButton("Boot Image")
        self.boot_no_flash_button.setToolTip("Boot boot/recovery.img without flashing (Fastboot mode)")
        button_grid[1].addWidget(self.boot_no_flash_button)

        self.sideload_button = QPushButton("ADB Sideload ZIP")
        self.sideload_button.setToolTip("Flash ZIP via ADB Sideload (Recovery/Sideload mode)")
        button_grid[1].addWidget(self.sideload_button)


        # Row 3: Reboot & File Ops
        self.reboot_system_button = QPushButton("Reboot System")
        self.reboot_system_button.setToolTip("Reboot to Android (ADB or Fastboot)")
        button_grid[2].addWidget(self.reboot_system_button)

        self.reboot_recovery_button = QPushButton("Reboot Recovery")
        self.reboot_recovery_button.setToolTip("Reboot to recovery (ADB mode)")
        button_grid[2].addWidget(self.reboot_recovery_button)

        self.reboot_bootloader_button = QPushButton("Reboot Bootloader")
        self.reboot_bootloader_button.setToolTip("Reboot to bootloader/fastboot (ADB mode)")
        button_grid[2].addWidget(self.reboot_bootloader_button)

        self.adb_push_button = QPushButton("ADB Push File")
        self.adb_push_button.setToolTip("Push file to device (ADB mode)")
        button_grid[2].addWidget(self.adb_push_button)

        self.adb_pull_button = QPushButton("ADB Pull File")
        self.adb_pull_button.setToolTip("Pull file from device (ADB mode)")
        button_grid[2].addWidget(self.adb_pull_button)

        # Add button rows to main layout
        for row_layout in button_grid:
            main_layout.addLayout(row_layout)

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Initializing...")
        main_layout.addWidget(self.status_bar)

        # Set initial state for buttons (disconnected, not busy)
        self._update_button_states('none', False)
        logging.debug("MainWindow.init_ui finished.")

    def connect_signals(self):
        """Connect UI elements to handlers and manager signals to slots."""
        logging.debug("MainWindow.connect_signals started.")
        # --- Connect UI Buttons to Handlers in this Class ---
        self.detect_button.clicked.connect(self.handle_detect_click) # Fixed connection
        self.unlock_button.clicked.connect(self.handle_unlock_click)
        self.lock_button.clicked.connect(self.handle_lock_click)
        self.recovery_button.clicked.connect(lambda: self.handle_flash_click('recovery'))
        self.boot_button.clicked.connect(lambda: self.handle_flash_click('boot'))
        self.boot_no_flash_button.clicked.connect(self.handle_boot_click)
        self.sideload_button.clicked.connect(self.handle_sideload_click)
        self.reboot_system_button.clicked.connect(lambda: self.handle_reboot_click('system'))
        self.reboot_recovery_button.clicked.connect(lambda: self.handle_reboot_click('recovery'))
        self.reboot_bootloader_button.clicked.connect(lambda: self.handle_reboot_click('bootloader'))
        self.adb_push_button.clicked.connect(self.handle_push_click)
        self.adb_pull_button.clicked.connect(self.handle_pull_click)

        # --- Connect DeviceManager Signals to Slots in this Class ---
        self.device_manager.device_state_updated.connect(self.update_ui_for_device_state)
        self.device_manager.log_request.connect(self.log_to_output)
        self.device_manager.command_started.connect(self.on_command_started)
        self.device_manager.command_output_received.connect(self.on_command_output)
        self.device_manager.command_finished.connect(self.on_command_finished)
        self.device_manager.command_error_occurred.connect(self.on_command_error)
        logging.debug("MainWindow.connect_signals finished.")


    # --- Button Click Handlers (Delegate to DeviceManager) ---

    # --- THIS METHOD WAS MISSING ---
    def handle_detect_click(self):
        """Handles the 'Detect Device' button click."""
        # Optional: Log the click itself for debugging
        self.log_to_output("Detect button clicked.", LOG_LEVEL_DEBUG, "Detecting...")
        self.device_manager.detect_device_details() # Delegate to the manager
    # --- END OF MISSING METHOD ---

    def _confirm_action(self, title, message, warning_level=QMessageBox.Warning):
        """Shows a confirmation dialog. Returns True if Yes."""
        msgBox = QMessageBox(self)
        msgBox.setWindowTitle(title)
        msgBox.setText(message)
        msgBox.setIcon(warning_level)
        msgBox.addButton(QMessageBox.Yes)
        msgBox.addButton(QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.No)
        reply = msgBox.exec_()
        return reply == QMessageBox.Yes

    def handle_unlock_click(self):
        """Handles the 'Unlock Bootloader' button click."""
        if self.device_manager.device_mode != 'fastboot':
             self.log_to_output("Action requires Fastboot mode.", LOG_LEVEL_ERROR, "Wrong mode")
             QMessageBox.warning(self, "Mode Error", "Unlock requires Fastboot mode.")
             return
        warning = self.device_manager.get_config_value('unlock_warning', "Unlocking will wipe data!")
        if self._confirm_action("Unlock Bootloader - DATA WIPE WARNING",
                                f"{warning}\n\nThis usually ERASES ALL DATA and may void warranty.\n\nProceed?",
                                QMessageBox.Critical):
            self.log_to_output("User confirmed unlock.", LOG_LEVEL_WARNING, None)
            self.device_manager.execute_unlock()
        else:
            self.log_to_output("Unlock cancelled by user.", LOG_LEVEL_INFO, "Unlock cancelled.")

    def handle_lock_click(self):
        """Handles the 'Lock Bootloader' button click."""
        if self.device_manager.device_mode != 'fastboot':
             self.log_to_output("Action requires Fastboot mode.", LOG_LEVEL_ERROR, "Wrong mode")
             QMessageBox.warning(self, "Mode Error", "Lock requires Fastboot mode.")
             return
        warning = self.device_manager.get_config_value('lock_warning', "Locking might wipe data!")
        if self._confirm_action("Lock Bootloader - Warning",
                                f"{warning}\n\nEnsure stock firmware is installed before locking!\n\nProceed?",
                                QMessageBox.Warning):
            self.log_to_output("User confirmed lock.", LOG_LEVEL_WARNING, None)
            self.device_manager.execute_lock()
        else:
            self.log_to_output("Lock cancelled by user.", LOG_LEVEL_INFO, "Lock cancelled.")


    def handle_flash_click(self, partition_type):
        """Handles clicks for 'Flash Recovery' and 'Flash Boot'."""
        if self.device_manager.device_mode != 'fastboot':
             self.log_to_output(f"Flash {partition_type} requires Fastboot mode.", LOG_LEVEL_ERROR, "Wrong mode")
             QMessageBox.warning(self, "Mode Error", f"Flash {partition_type} requires Fastboot mode.")
             return
        partition_name = self.device_manager.get_config_value(f'{partition_type}_partition', partition_type)
        file_path, _ = QFileDialog.getOpenFileName(self, f"Select {partition_type.capitalize()} Image (.img) for '{partition_name}'", "", "Image Files (*.img);;All Files (*)")
        if not file_path:
            self.log_to_output(f"{partition_type.capitalize()} flash cancelled - no file.", LOG_LEVEL_INFO, "Flash cancelled.")
            return

        if self._confirm_action(f"Confirm Flash {partition_type.capitalize()}",
                                f"Flash '{os.path.basename(file_path)}' to '{partition_name}'?\n\nWARNING: Incorrect images can BRICK your device!",
                                QMessageBox.Warning):
            self.log_to_output(f"User confirmed flash {partition_type}.", LOG_LEVEL_WARNING, None)
            self.device_manager.execute_flash(partition_type, file_path)
        else:
            self.log_to_output(f"{partition_type.capitalize()} flash cancelled by user.", LOG_LEVEL_INFO, "Flash cancelled.")


    def handle_boot_click(self):
        """Handles the 'Boot Image (No Flash)' button click."""
        if self.device_manager.device_mode != 'fastboot':
             self.log_to_output("Boot Image requires Fastboot mode.", LOG_LEVEL_ERROR, "Wrong mode")
             QMessageBox.warning(self, "Mode Error", "Boot Image requires Fastboot mode.")
             return
        file_path, _ = QFileDialog.getOpenFileName(self, f"Select Boot/Recovery Image (.img) to Boot", "", "Image Files (*.img);;All Files (*)")
        if not file_path:
            self.log_to_output("Boot image cancelled - no file selected.", LOG_LEVEL_INFO, "Boot cancelled.")
            return

        if self._confirm_action("Confirm Boot Image",
                                f"Boot '{os.path.basename(file_path)}' without flashing?\n\nDevice will boot this image once. Ensure it's compatible!",
                                QMessageBox.Question):
            self.log_to_output("User confirmed boot image.", LOG_LEVEL_INFO, None)
            self.device_manager.execute_boot_image(file_path)
        else:
            self.log_to_output("Boot image cancelled by user.", LOG_LEVEL_INFO, "Boot cancelled.")

    def handle_sideload_click(self):
        """Handles the 'ADB Sideload ZIP' button click."""
        if self.device_manager.device_mode != 'sideload':
             self.log_to_output("Sideload requires Recovery/Sideload mode.", LOG_LEVEL_ERROR, "Wrong mode")
             QMessageBox.warning(self, "Mode Error", "ADB Sideload requires the device to be in Recovery mode with Sideload active.")
             return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select ZIP File for Sideload", "", "ZIP Files (*.zip);;All Files (*)")
        if not file_path:
            self.log_to_output("Sideload cancelled - no file selected.", LOG_LEVEL_INFO, "Sideload cancelled.")
            return

        if self._confirm_action("Confirm ADB Sideload",
                                f"Sideload '{os.path.basename(file_path)}'?\n\nEnsure device is in ADB Sideload mode!",
                                QMessageBox.Question):
            self.log_to_output("User confirmed ADB Sideload.", LOG_LEVEL_WARNING, None)
            self.device_manager.execute_sideload(file_path)
        else:
            self.log_to_output("ADB Sideload cancelled by user.", LOG_LEVEL_INFO, "Sideload cancelled.")


    def handle_reboot_click(self, target):
        """Handles clicks for reboot buttons."""
        # No confirmation for reboots unless desired
        if not self.device_manager.execute_reboot(target):
            # execute_reboot logs the error if it can't run
            pass


    def handle_push_click(self):
        """Handles the 'ADB Push File' button click."""
        if self.device_manager.device_mode != 'adb':
             self.log_to_output("Push requires ADB mode.", LOG_LEVEL_ERROR, "Wrong mode")
             QMessageBox.warning(self, "Mode Error", "ADB Push requires ADB mode.")
             return
        local_path, _ = QFileDialog.getOpenFileName(self, "Select Local File to Push", "", "All Files (*)")
        if not local_path:
            self.log_to_output("Push cancelled - no local file.", LOG_LEVEL_INFO, "Push cancelled.")
            return

        device_path, ok = QInputDialog.getText(self, "Device Destination Path",
                                               "Enter full path on device (e.g., /sdcard/Download/):")
        if not ok or not device_path:
            self.log_to_output("Push cancelled - no device path.", LOG_LEVEL_INFO, "Push cancelled.")
            return

        if self._confirm_action("Confirm ADB Push",
                                f"Push '{os.path.basename(local_path)}' to '{device_path}'?",
                                QMessageBox.Question):
            self.log_to_output("User confirmed ADB Push.", LOG_LEVEL_INFO, None)
            self.device_manager.execute_push(local_path, device_path)
        else:
            self.log_to_output("ADB Push cancelled by user.", LOG_LEVEL_INFO, "Push cancelled.")

    def handle_pull_click(self):
        """Handles the 'ADB Pull File' button click."""
        if self.device_manager.device_mode != 'adb':
             self.log_to_output("Pull requires ADB mode.", LOG_LEVEL_ERROR, "Wrong mode")
             QMessageBox.warning(self, "Mode Error", "ADB Pull requires ADB mode.")
             return
        device_path, ok = QInputDialog.getText(self, "Device Source Path",
                                               "Enter full path of file on device (e.g., /sdcard/file.zip):")
        if not ok or not device_path:
            self.log_to_output("Pull cancelled - no device path.", LOG_LEVEL_INFO, "Pull cancelled.")
            return

        suggested_filename = os.path.basename(device_path) if device_path else "pulled_file"
        local_path, _ = QFileDialog.getSaveFileName(self, "Select Local Destination", suggested_filename, "All Files (*)")
        if not local_path:
            self.log_to_output("Pull cancelled - no local destination.", LOG_LEVEL_INFO, "Pull cancelled.")
            return

        if self._confirm_action("Confirm ADB Pull",
                                f"Pull '{device_path}' to '{os.path.basename(local_path)}'?",
                                QMessageBox.Question):
            self.log_to_output("User confirmed ADB Pull.", LOG_LEVEL_INFO, None)
            self.device_manager.execute_pull(device_path, local_path)
        else:
            self.log_to_output("ADB Pull cancelled by user.", LOG_LEVEL_INFO, "Pull cancelled.")


    # --- Slots for DeviceManager Signals ---

    @pyqtSlot(str, str, str, str)
    def update_ui_for_device_state(self, mode, serial, manufacturer, model):
        """Updates labels and button enabled state based on device manager signal."""
        logging.debug(f"Slot update_ui_for_device_state: mode={mode}, serial={serial}, mfr={manufacturer}, model={model}")
        self.mode_label.setText(f"Mode: {mode.capitalize()}")
        self.serial_label.setText(f"Serial: {serial if serial else 'N/A'}")
        self.manufacturer_label.setText(f"Manufacturer: {manufacturer if manufacturer else 'Unknown'}")
        self.model_label.setText(f"Model: {model if model else 'Unknown'}")

        # Button states depend on mode and busy status
        is_busy = self.device_manager.is_busy()
        self._update_button_states(mode, is_busy)

    @pyqtSlot(str, int, str)
    def log_to_output(self, message, level, status_msg):
        """Logs message to the text area and optionally updates status bar."""
        prefix_map = {
            LOG_LEVEL_CRITICAL: "[CRIT]  ",
            LOG_LEVEL_ERROR:    "[ERROR] ",
            LOG_LEVEL_WARNING:  "[WARN]  ",
            LOG_LEVEL_INFO:     "[INFO]  ",
            LOG_LEVEL_DEBUG:    "[DEBUG] ",
            OUTPUT_TYPE_STDOUT: "[OUT]   ",
            OUTPUT_TYPE_STDERR: "[ERR]   ",
        }
        # Determine prefix: Use level if available, otherwise assume INFO
        # (Note: Command output uses level=INFO/WARN currently)
        prefix = prefix_map.get(level, prefix_map[LOG_LEVEL_INFO])

        # Log to file first (configured in main.py)
        log_func = logging.getLogger().log
        log_func(level, message)

        # Append to GUI text area - Ensure this runs on the main thread
        # Signals are usually queued, but QTimer ensures it if needed.
        # QTimer.singleShot(0, lambda: self._append_text(prefix + message + '\n'))
        self._append_text(prefix + message + '\n')

        # Update status bar - Ensure this runs on the main thread
        if status_msg is not None: # Allow empty string "" as a message
            # QTimer.singleShot(0, lambda msg=status_msg: self.status_bar.showMessage(msg, 5000))
            self.status_bar.showMessage(status_msg, 5000) # Show for 5 seconds

    def _append_text(self, text):
        """Safely appends text to the output area and scrolls."""
        cursor = self.output_text.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(text)
        self.output_text.ensureCursorVisible() # Auto-scroll

    @pyqtSlot(str)
    def on_command_started(self, command_str):
        """Called when the device manager starts a command."""
        logging.debug(f"Slot on_command_started: {command_str}")
        is_busy = True
        mode = self.device_manager.device_mode
        self._update_button_states(mode, is_busy)
        # Status bar message is set by the log_request signal with status_during

    @pyqtSlot(str, str)
    def on_command_output(self, output_type, line):
        """Logs output received from the running command."""
        # Map type to log level for consistent prefixing via log_to_output
        level = LOG_LEVEL_INFO # stdout is INFO
        if output_type == OUTPUT_TYPE_STDERR:
            # Often not a true error for adb/fastboot, treat as warning or info
            level = LOG_LEVEL_WARNING

        self.log_to_output(line, level, None) # No status bar update for intermediate output

    @pyqtSlot(bool, str)
    def on_command_finished(self, success, command_str):
        """Called when the device manager reports a command finished."""
        logging.debug(f"Slot on_command_finished: success={success}, cmd={command_str}")
        is_busy = False
        mode = self.device_manager.device_mode
        self._update_button_states(mode, is_busy)
        # Final status bar message handled by log_request from manager's finish logic

    @pyqtSlot(str, str)
    def on_command_error(self, user_message, command_str):
         """Logs an error message received from the device manager/worker."""
         logging.debug(f"Slot on_command_error: msg={user_message}, cmd={command_str}")
         # Log as ERROR level, status bar indicates general command error
         self.log_to_output(user_message, LOG_LEVEL_ERROR, "Command Error!")
         # Button state updated by on_command_finished which always follows


    def _update_button_states(self, mode, is_busy):
        """Enables/disables buttons based on mode and busy state."""
        logging.debug(f"Updating button states: mode={mode}, is_busy={is_busy}")
        is_adb = mode == 'adb'
        is_fastboot = mode == 'fastboot'
        is_sideload = mode == 'sideload'

        # Enable detect unless busy
        self.detect_button.setEnabled(not is_busy)

        # Fastboot specific
        self.unlock_button.setEnabled(is_fastboot and not is_busy)
        self.lock_button.setEnabled(is_fastboot and not is_busy)
        self.recovery_button.setEnabled(is_fastboot and not is_busy)
        self.boot_button.setEnabled(is_fastboot and not is_busy)
        self.boot_no_flash_button.setEnabled(is_fastboot and not is_busy)

        # Sideload specific
        self.sideload_button.setEnabled(is_sideload and not is_busy)

        # ADB specific
        self.reboot_recovery_button.setEnabled(is_adb and not is_busy)
        self.reboot_bootloader_button.setEnabled(is_adb and not is_busy)
        self.adb_push_button.setEnabled(is_adb and not is_busy)
        self.adb_pull_button.setEnabled(is_adb and not is_busy)

        # ADB or Fastboot
        self.reboot_system_button.setEnabled((is_adb or is_fastboot) and not is_busy)


    # --- Cleanup ---
    def closeEvent(self, event):
        """Handle application closing."""
        if self.device_manager.is_busy():
            if self._confirm_action("Confirm Exit",
                                    "A command is running.\nAbort command and exit?",
                                    QMessageBox.Question):
                logging.warning("User requested exit during active command.")
                self.device_manager.abort_current_command()
                self.device_manager.stop_monitoring() # Stop timer
                event.accept()
                logging.info("Application closing after abort.")
            else:
                event.ignore()
                logging.debug("Application close cancelled by user.")
                return # Important to return here
        else:
            self.device_manager.stop_monitoring() # Stop timer
            logging.info("Application closing normally.")
            event.accept()