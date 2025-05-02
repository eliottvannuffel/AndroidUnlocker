import subprocess
import sys
import os
import yaml  # Requires PyYAML: pip install PyYAML
import logging
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QFileDialog, QLabel,
                             QMessageBox, QStatusBar)
from PyQt5.QtCore import Qt, QTimer
# from PyQt5.QtGui import QFontDatabase # QFontDatabase was imported but not used, can be removed.

# Import qt_material *after* PyQt5 imports
from qt_material import apply_stylesheet  # Material Design library

# --- Configuration ---
YAML_FILE_PATH = "devices.yaml"
LOG_FILE_PATH = "bootloader_tool.log"
COMMAND_TIMEOUT = 30  # Default timeout in seconds

# --- Setup Logging ---
logging.basicConfig(filename=LOG_FILE_PATH, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class BootloaderTool(QWidget):
    def __init__(self):
        super().__init__()
        self.device_config = None  # To store loaded config for detected device
        self.load_device_database()
        self.init_ui()
        logging.info("Application started.")

    def load_device_database(self):
        self.device_db = {}
        # Define a robust default configuration
        default_config = {
            'unlock_command': "fastboot oem unlock",
            'lock_command': "fastboot oem lock",
            'recovery_partition': "recovery",
            'boot_partition': "boot",
            'unlock_warning': "Unlocking the bootloader will wipe all user data (factory reset) and may void your warranty! Proceed with caution.",
            'lock_warning': "Locking the bootloader will wipe all user data. Ensure you have backups before proceeding.",
            'notes': 'Using default configuration. Device-specific commands may differ.'
        }

        try:
            if os.path.exists(YAML_FILE_PATH):
                with open(YAML_FILE_PATH, 'r') as f:
                    try:
                        loaded_db = yaml.safe_load(f)
                        if not isinstance(loaded_db, dict):
                             # If YAML is invalid structure, log error and use only default
                            logging.error(f"Invalid YAML structure in {YAML_FILE_PATH}: Expected a dictionary.")
                            QMessageBox.warning(self, "Error", f"Invalid YAML structure in {YAML_FILE_PATH}. Using default commands only.")
                            self.device_db['default'] = default_config # Fallback to default
                        else:
                            self.device_db = loaded_db
                            # Ensure default exists even if file is loaded but missing 'default'
                            if 'default' not in self.device_db:
                                self.device_db['default'] = default_config
                                logging.warning("'default' entry not found in YAML. Using built-in default.")
                            logging.info(f"Loaded device database from {YAML_FILE_PATH}")

                    except yaml.YAMLError as e:
                        logging.error(f"Error parsing YAML file {YAML_FILE_PATH}: {e}", exc_info=True)
                        QMessageBox.warning(self, "Error", f"Could not parse {YAML_FILE_PATH}.\n{e}\nUsing default commands only.")
                        self.device_db['default'] = default_config # Fallback to default
                    except Exception as e:
                         # Catch any other unexpected errors during file read/parse
                        logging.error(f"Unexpected error loading {YAML_FILE_PATH}: {e}", exc_info=True)
                        QMessageBox.warning(self, "Error", f"Unexpected error loading {YAML_FILE_PATH}.\n{e}\nUsing default commands only.")
                        self.device_db['default'] = default_config # Fallback to default

                if not self.device_db and os.path.exists(YAML_FILE_PATH): # Case where file exists but is empty or only whitespace
                     logging.warning(f"{YAML_FILE_PATH} is empty or invalid. Using default commands only.")
                     self.device_db['default'] = default_config

            else:
                logging.warning(f"{YAML_FILE_PATH} not found. Using default commands only.")
                # Create a default entry if file doesn't exist
                self.device_db['default'] = default_config

        except Exception as e: # Catch errors related to file opening or initial setup
            logging.error(f"Critical error during database loading: {e}", exc_info=True)
            QMessageBox.critical(self, "Critical Error", f"A critical error occurred while loading the device database.\n{e}\nThe application may not function correctly.")
            # Ensure default exists even on critical error
            if 'default' not in self.device_db:
                 self.device_db['default'] = default_config


    def init_ui(self):
        self.setWindowTitle("Enhanced Android Bootloader & Recovery Tool")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        # --- Device Info Area ---
        self.info_layout = QHBoxLayout()
        self.manufacturer_label = QLabel("Manufacturer: Unknown")
        self.model_label = QLabel("Model: Unknown")
        self.info_layout.addWidget(self.manufacturer_label)
        self.info_layout.addWidget(self.model_label)
        layout.addLayout(self.info_layout)

        # --- Output Area ---
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Command output and logs will appear here...")
        layout.addWidget(self.output)

        # --- Buttons ---
        self.button_layout = QHBoxLayout()

        self.detect_button = QPushButton("Detect Device Details")
        self.detect_button.clicked.connect(self.detect_device_details)
        self.button_layout.addWidget(self.detect_button)

        self.unlock_button = QPushButton("Unlock Bootloader")
        self.unlock_button.setToolTip("Attempt to unlock the bootloader (Requires device in Fastboot mode). Wipes data!")
        self.unlock_button.clicked.connect(self.unlock_bootloader)
        self.button_layout.addWidget(self.unlock_button)

        self.lock_button = QPushButton("Lock Bootloader")
        self.lock_button.setToolTip("Lock the bootloader (Requires device in Fastboot mode).")
        self.lock_button.clicked.connect(self.lock_bootloader)
        self.button_layout.addWidget(self.lock_button)

        # FIX: Connect the button to the missing methods
        self.recovery_button = QPushButton("Flash Recovery")
        self.recovery_button.setToolTip("Flash a custom recovery image (Requires device in Fastboot mode)")
        self.recovery_button.clicked.connect(self.flash_recovery) # This needs the flash_recovery method
        self.button_layout.addWidget(self.recovery_button)

        layout.addLayout(self.button_layout)

        self.button_layout2 = QHBoxLayout()

        # FIX: Connect the button to the missing methods
        self.sideload_button = QPushButton("ADB Sideload ROM/ZIP")
        self.sideload_button.setToolTip("Flash a ROM or ZIP file via ADB Sideload (Requires device in Recovery mode with Sideload active)")
        self.sideload_button.clicked.connect(self.flash_rom_sideload) # This needs the flash_rom_sideload method
        self.button_layout2.addWidget(self.sideload_button)

        # FIX: Connect the button to the missing methods
        self.magisk_button = QPushButton("Flash Patched Boot (Magisk)")
        self.magisk_button.setToolTip("Flash a boot image previously patched by Magisk (Requires device in Fastboot mode)")
        self.magisk_button.clicked.connect(self.flash_patched_boot) # This needs the flash_patched_boot method
        self.button_layout2.addWidget(self.magisk_button)

        layout.addLayout(self.button_layout2)

        # --- Status Bar ---
        self.statusBar = QStatusBar()
        self.statusBar.showMessage("Ready. Ensure ADB/Fastboot drivers are installed.")
        layout.addWidget(self.statusBar)

        self.setLayout(layout)

    def log_and_append(self, message, level=logging.INFO, status_msg=None):
        """Helper to log message and append to GUI output."""
        # Use a QTimer.singleShot to ensure GUI update happens on the main thread
        # This prevents potential threading issues with logging/appending from subprocess calls
        QTimer.singleShot(0, lambda: self._append_to_output(message, level, status_msg))

    def _append_to_output(self, message, level, status_msg):
        """Internal method to safely append to QTextEdit from potentially other contexts."""
        if level == logging.ERROR:
            logging.error(message)
            self.output.append(f"<font color='red'>[ERROR]</font> {message}")
        elif level == logging.WARNING:
            logging.warning(message)
            self.output.append(f"<font color='orange'>[WARNING]</font> {message}")
        else:
            logging.info(message)
            self.output.append(f"[*] {message}")

        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())  # Auto-scroll
        if status_msg:
            # Use QTimer for status bar updates too
            QTimer.singleShot(0, lambda: self.statusBar.showMessage(status_msg, 5000)) # Show for 5 seconds


    def run_command(self, command, success_msg=None, error_msg_prefix=None, timeout=COMMAND_TIMEOUT):
        """Runs a shell command and returns the output and success status."""
        self.log_and_append(f"Executing command: {command}")
        try:
            # Use subprocess.run for simpler timeout handling and capturing output
            process = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            stdout = process.stdout.strip()
            stderr = process.stderr.strip()

            if process.returncode == 0:
                if success_msg:
                    self.log_and_append(success_msg)
                if stdout:
                    self.log_and_append(f"Output:\n{stdout}")
                return stdout, True
            else:
                error_msg = f"{error_msg_prefix}: {stderr}" if error_msg_prefix else stderr
                full_error_log = f"Command failed with return code {process.returncode}.\nStderr: {stderr}\nStdout: {stdout}"
                self.log_and_append(error_msg, level=logging.ERROR)
                logging.error(full_error_log) # Log full details
                return error_msg, False
        except FileNotFoundError:
            msg = f"Error: Command not found. Is ADB/Fastboot installed and in your PATH?"
            self.log_and_append(msg, level=logging.ERROR, status_msg=msg)
            logging.error(msg, exc_info=True)
            return msg, False
        except subprocess.TimeoutExpired:
            msg = f"Command timed out after {timeout} seconds: {command}"
            self.log_and_append(msg, level=logging.ERROR, status_msg="Command timed out.")
            logging.error(msg, exc_info=True)
            return "Timeout", False
        except Exception as e:
            msg = f"Error running command: {e}"
            self.log_and_append(msg, level=logging.ERROR, status_msg="Error executing command.")
            logging.error(msg, exc_info=True)
            return str(e), False

    def get_device_property(self, prop_name):
        """Gets an Android property using adb shell getprop."""
        command = f"adb shell getprop {prop_name}"
        output, success = self.run_command(command, None, f"Failed to get property {prop_name}")
        if success:
             # ADB getprop might return the property value followed by a newline, strip it
            return output.strip()
        return None


    def detect_device_details(self):
        """Detects manufacturer and model using ADB."""
        try:
            self.log_and_append("Attempting to detect device details via ADB...", status_msg="Detecting device...")

            # Check if *any* ADB device is connected first
            adb_devices_output, adb_devices_success = self.run_command("adb devices", None, "Failed to list ADB devices")

            # Simple check for "List of devices attached" followed by at least one device line
            if not adb_devices_success or "List of devices attached" not in adb_devices_output or len(adb_devices_output.splitlines()) <= 1:
                 self.log_and_append("No ADB devices found. Ensure device is connected and authorized for ADB.", level=logging.ERROR)
                 self.statusBar.showMessage("No ADB device found.", 5000)
                 # Reset labels and config if no device found
                 self.manufacturer_label.setText("Manufacturer: Unknown")
                 self.model_label.setText("Model: Unknown")
                 self.device_config = None # Explicitly clear device config
                 return

            # Wait for the device state to be "device" (normal ADB mode)
            self.log_and_append("Waiting for ADB device state...", status_msg="Waiting for ADB state...")
            wait_output, wait_success = self.run_command("adb wait-for-device", "ADB device state is 'device'.", "Waiting for ADB device failed")
            if not wait_success:
                 self.log_and_append("ADB wait-for-device failed. Device may not be in the correct state or authorized.", level=logging.ERROR)
                 self.statusBar.showMessage("ADB wait failed.", 5000)
                 self.manufacturer_label.setText("Manufacturer: Unknown")
                 self.model_label.setText("Model: Unknown")
                 self.device_config = None
                 return


            # Get manufacturer and model properties
            manufacturer = self.get_device_property("ro.product.manufacturer")
            model = self.get_device_property("ro.product.model")

            if manufacturer and model:
                self.manufacturer_label.setText(f"Manufacturer: {manufacturer}")
                self.model_label.setText(f"Model: {model}")
                self.device_config = self.find_device_config(manufacturer, model)
                self.log_and_append(f"Detected device: {manufacturer} {model}", status_msg=f"Detected: {manufacturer} {model}")
                config_source = "YAML" if self.device_config != self.device_db.get('default') else "Default"
                self.log_and_append(f"Using device configuration: {config_source}")

                if self.device_config and 'notes' in self.device_config:
                    self.log_and_append(f"Device Notes: {self.device_config['notes']}", level=logging.WARNING)
                self.statusBar.showMessage(f"Detected: {manufacturer} {model}", 5000)
            elif manufacturer:
                self.manufacturer_label.setText(f"Manufacturer: {manufacturer}")
                self.model_label.setText("Model: Unknown")
                self.device_config = self.find_device_config(manufacturer, None) # Try matching by manufacturer alone
                self.log_and_append("Could not detect device model. Attempting manufacturer match or using default configuration.", level=logging.WARNING)
                config_source = "YAML (Manufacturer Match)" if self.device_config and self.device_config != self.device_db.get('default') else "Default"
                self.log_and_append(f"Using configuration: {config_source}")
                if self.device_config and 'notes' in self.device_config:
                    self.log_and_append(f"Device Notes: {self.device_config['notes']}", level=logging.WARNING)
                self.statusBar.showMessage("Detected Manufacturer, but failed to get Model.", 5000)
            else:
                self.manufacturer_label.setText("Manufacturer: Unknown")
                self.model_label.setText("Model: Unknown")
                self.device_config = self.device_db.get('default')  # Use default if no detection
                self.log_and_append("Failed to detect device details. Ensure ADB debugging is enabled and authorized.", level=logging.ERROR)
                self.log_and_append("Using default configuration.", level=logging.WARNING)
                self.statusBar.showMessage("Device detection failed.", 5000)
        except Exception as e:
            self.log_and_append(f"An error occurred while detecting device details: {e}", level=logging.ERROR)
            self.statusBar.showMessage("Error detecting device details. Check logs for details.", 5000)
            self.device_config = self.device_db.get('default') # Ensure config is at least default on error

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
             manufacturer_key = manufacturer.lower() # Match manufacturer name as a key
             if manufacturer_key in self.device_db:
                 logging.info(f"Found manufacturer match in config for '{manufacturer_key}'")
                 return self.device_db[manufacturer_key]

        logging.warning(f"No specific config found for Manufacturer='{manufacturer}', Model='{model}'. Using default.")
        return self.device_db.get('default')  # Fallback to default configuration


    def unlock_bootloader(self):
        """Handles the bootloader unlock process with warnings."""
        self.log_and_append("Starting bootloader unlock process...", status_msg="Starting unlock...")

        # Ensure we have some config (at least default)
        config = self.device_config or self.device_db.get('default')
        if not config:
            QMessageBox.critical(self, "Error", "No device configuration found, cannot proceed.")
            self.log_and_append("Unlock failed: Missing device configuration.", level=logging.ERROR)
            self.statusBar.showMessage("Unlock failed: No config.", 5000)
            return

        unlock_command_template = config.get('unlock_command', 'fastboot oem unlock')  # Default unlock command
        warning_message = config.get(
            'unlock_warning',
            "Unlocking the bootloader will erase all data on the device. Ensure you have backups before proceeding."
        )

        # --- Show CRITICAL Warning ---
        reply = QMessageBox.warning(self, "Unlock Bootloader - WARNING",
                                    f"{warning_message}\n\n"
                                    "THIS ACTION CANNOT BE UNDONE AND WILL ERASE YOUR PHONE.\n\n"
                                    "Do you want to proceed?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.log_and_append("Bootloader unlock cancelled by user.", status_msg="Unlock cancelled.")
            self.statusBar.showMessage("Unlock cancelled.", 5000)
            return

        self.log_and_append("User confirmed unlock warning.", level=logging.WARNING)

        # --- Reboot to Bootloader ---
        self.log_and_append("Rebooting device to bootloader...", status_msg="Rebooting to bootloader...")
        # Give a bit more timeout for reboot, although fastboot wait should handle the rest
        output_reboot, success_reboot = self.run_command("adb reboot bootloader", "Reboot command sent. Waiting for device in fastboot...", "Failed to send reboot command", timeout=45)

        # --- Wait and Check Fastboot ---
        # Wait explicitly for fastboot device after sending reboot command
        self.log_and_append("Waiting for device to appear in fastboot mode...", status_msg="Waiting for fastboot...")
        self.wait_for_fastboot() # This method already logs success/failure


        # --- Send Unlock Command ---
        # Some devices need specific unlock commands, e.g., 'fastboot flashing unlock'
        # The config file should specify this. Use the template from config.
        # If the command needs arguments (like device-specific unlock codes),
        # the YAML or a separate input might be needed. For now, assume simple commands.
        unlock_command = unlock_command_template.format(manufacturer=self.manufacturer_label.text().split(': ')[1],
                                                         model=self.model_label.text().split(': ')[1]) # Basic formatting attempt

        self.log_and_append(f"Sending unlock command: {unlock_command}", status_msg="Sending unlock command...")
        self.run_command(unlock_command, "Unlock command sent.", "Failed to send unlock command")
        self.log_and_append("IMPORTANT: You likely need to confirm the unlock on your device's screen if prompted!", level=logging.WARNING)


    def lock_bootloader(self):
        """Handles the bootloader lock process with warnings."""
        self.log_and_append("Starting bootloader lock process...", status_msg="Starting lock...")

        # Ensure we have some config (at least default)
        config = self.device_config or self.device_db.get('default')
        if not config:
            QMessageBox.critical(self, "Error", "No device configuration found, cannot proceed.")
            self.log_and_append("Lock failed: Missing device configuration.", level=logging.ERROR)
            self.statusBar.showMessage("Lock failed: No config.", 5000)
            return

        lock_command_template = config.get('lock_command', 'fastboot oem lock')  # Default lock command
        warning_message = config.get(
            'lock_warning',
            "Locking the bootloader will erase all data on the device. Ensure you have backups before proceeding."
        )

        # --- Show CRITICAL Warning ---
        reply = QMessageBox.warning(self, "Lock Bootloader - WARNING",
                                    f"{warning_message}\n\n"
                                    "THIS ACTION CANNOT BE UNDONE AND WILL ERASE YOUR PHONE.\n\n"
                                    "Do you want to proceed?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.log_and_append("Bootloader lock cancelled by user.", status_msg="Lock cancelled.")
            self.statusBar.showMessage("Lock cancelled.", 5000)
            return

        self.log_and_append("User confirmed lock warning.", level=logging.WARNING)

         # --- Reboot to Bootloader ---
        self.log_and_append("Rebooting device to bootloader...", status_msg="Rebooting to bootloader...")
        output_reboot, success_reboot = self.run_command("adb reboot bootloader", "Reboot command sent. Waiting for device in fastboot...", "Failed to send reboot command", timeout=45)

        # --- Wait and Check Fastboot ---
        self.log_and_append("Waiting for device to appear in fastboot mode...", status_msg="Waiting for fastboot...")
        self.wait_for_fastboot() # This method already logs success/failure


        # --- Send Lock Command ---
        lock_command = lock_command_template.format(manufacturer=self.manufacturer_label.text().split(': ')[1],
                                                    model=self.model_label.text().split(': ')[1]) # Basic formatting attempt

        self.log_and_append(f"Sending lock command: {lock_command}", status_msg="Sending lock command...")
        self.run_command(lock_command, "Lock command sent.", "Failed to send lock command")
        self.log_and_append("IMPORTANT: You likely need to confirm the lock on your device's screen if prompted!", level=logging.WARNING)


    def wait_for_fastboot(self):
        """Waits for the device to enter Fastboot mode."""
        self.log_and_append("Checking for Fastboot device...", status_msg="Checking fastboot...")
        # Use 'fastboot devices' and check output. It returns empty or list of devices.
        # We need to wait until it *does* return a device.
        attempts = 0
        max_attempts = 10 # Wait up to 10 * 5 seconds = 50 seconds
        wait_time_sec = 5

        while attempts < max_attempts:
            output, success = self.run_command("fastboot devices", None, "Failed to list Fastboot devices (attempt)")
            # 'fastboot devices' output format: <serial_number>\tfastboot
            if success and output and "fastboot" in output:
                self.log_and_append("Device detected in Fastboot mode.", status_msg="Fastboot device found.")
                return True
            else:
                attempts += 1
                self.log_and_append(f"Fastboot device not found (attempt {attempts}/{max_attempts}). Waiting {wait_time_sec} seconds...", level=logging.WARNING, status_msg=f"Waiting for fastboot... ({attempts})")
                QApplication.processEvents() # Keep GUI responsive
                QTimer().singleShot(wait_time_sec * 1000, lambda: None) # Simple wait, or use QEventLoop
                # A more robust wait would involve a QTimer firing periodically

        self.log_and_append("Timed out waiting for device in Fastboot mode.", level=logging.ERROR, status_msg="Fastboot wait timed out.")
        QMessageBox.warning(self, "Fastboot Timeout", "Timed out waiting for the device to enter Fastboot mode.\nEnsure the device is correctly connected and in Fastboot.")
        return False

    # --- Add the missing methods here ---

    def flash_recovery(self):
        """Handles flashing a recovery image."""
        self.log_and_append("Starting recovery flashing process...", status_msg="Starting recovery flash...")

        config = self.device_config or self.device_db.get('default')
        if not config:
            QMessageBox.critical(self, "Error", "No device configuration found, cannot proceed.")
            self.log_and_append("Flash failed: Missing device configuration.", level=logging.ERROR)
            self.statusBar.showMessage("Flash failed: No config.", 5000)
            return

        recovery_partition = config.get('recovery_partition', 'recovery') # Default partition name

        # --- Get File Path ---
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Recovery Image (.img)", "", "Image Files (*.img);;All Files (*)")
        if not file_path:
            self.log_and_append("File selection cancelled.", status_msg="Flash cancelled.")
            return

        self.log_and_append(f"Selected file: {file_path}", status_msg="File selected.")

        # --- Show Confirmation ---
        reply = QMessageBox.question(self, "Confirm Flash Recovery",
                                     f"Are you sure you want to flash '{os.path.basename(file_path)}' to the '{recovery_partition}' partition?\n\n"
                                     "WARNING: Flashing an incorrect image can brick your device!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.log_and_append("Recovery flash cancelled by user.", status_msg="Flash cancelled.")
            return

        self.log_and_append("User confirmed recovery flash.", level=logging.WARNING)

        # --- Ensure Fastboot Mode ---
        if not self.wait_for_fastboot():
             self.log_and_append("Cannot proceed without device in Fastboot mode.", level=logging.ERROR)
             self.statusBar.showMessage("Flash failed: No Fastboot device.", 5000)
             return

        # --- Send Flash Command ---
        command = f"fastboot flash {recovery_partition} \"{file_path}\"" # Use quotes for paths with spaces
        self.log_and_append(f"Sending flash command: {command}", status_msg="Flashing recovery...")
        output, success = self.run_command(command, "Recovery flash command sent.", "Failed to send flash command")

        if success:
            self.log_and_append("Recovery flash command executed. Check device for status.", status_msg="Flash command sent.")
        else:
            self.log_and_append("Recovery flash command failed. Check output above for details.", level=logging.ERROR, status_msg="Flash command failed.")


    def flash_rom_sideload(self):
        """Handles flashing a ROM/ZIP via ADB Sideload."""
        self.log_and_append("Starting ADB Sideload process...", status_msg="Starting sideload...")

        # --- Show Instruction/Warning ---
        QMessageBox.information(self, "ADB Sideload Instructions",
                                "Ensure your device is in recovery mode and ADB Sideload is enabled!\n"
                                "This tool will now prompt you to select the ZIP file to sideload.\n\n"
                                "Click OK when your device is ready.", QMessageBox.Ok)


        # --- Get File Path ---
        file_path, _ = QFileDialog.getOpenFileName(self, "Select ROM/ZIP File (.zip)", "", "ZIP Files (*.zip);;All Files (*)")
        if not file_path:
            self.log_and_append("File selection cancelled.", status_msg="Sideload cancelled.")
            return

        self.log_and_append(f"Selected file: {file_path}", status_msg="File selected.")

        # --- Show Confirmation ---
        reply = QMessageBox.question(self, "Confirm ADB Sideload",
                                     f"Are you sure you want to sideload '{os.path.basename(file_path)}'?\n\n"
                                     "Ensure your device is in ADB Sideload mode!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.log_and_append("ADB Sideload cancelled by user.", status_msg="Sideload cancelled.")
            return

        self.log_and_append("User confirmed ADB Sideload.", level=logging.WARNING)

        # --- Ensure ADB Device is present (though state might be sideload) ---
        # 'adb devices' shows devices in sideload mode.
        self.log_and_append("Checking for ADB device...", status_msg="Checking ADB...")
        adb_check_output, adb_check_success = self.run_command("adb devices", None, "Failed to list ADB devices")
        if not adb_check_success or "sideload" not in adb_check_output:
             self.log_and_append("ADB device not found or not in sideload state. Ensure device is in recovery with sideload active.", level=logging.ERROR)
             self.statusBar.showMessage("Sideload failed: No ADB sideload device.", 5000)
             # Ask the user if they want to proceed anyway in case detection is flaky
             retry_sideload = QMessageBox.question(self, "Device Not Found/Sideload State",
                                                 "Could not detect an ADB device in 'sideload' state.\n"
                                                 "Please ensure your device is in recovery mode with sideload active.\n"
                                                 "Attempt sideload anyway?",
                                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
             if reply == QMessageBox.No:
                 self.log_and_append("ADB Sideload aborted due to device state check.", status_msg="Sideload aborted.")
                 return


        # --- Send Sideload Command ---
        command = f"adb sideload \"{file_path}\"" # Use quotes for paths with spaces
        self.log_and_append(f"Sending sideload command: {command}", status_msg="Starting sideload...")
        output, success = self.run_command(command, "ADB Sideload command sent. Check device for progress.", "Failed to send sideload command")

        if success:
            self.log_and_append("ADB Sideload command executed.", status_msg="Sideload command sent.")
        else:
            self.log_and_append("ADB Sideload command failed. Check output above for details.", level=logging.ERROR, status_msg="Sideload command failed.")


    def flash_patched_boot(self):
        """Handles flashing a patched boot image (e.g., for Magisk)."""
        self.log_and_append("Starting patched boot flashing process...", status_msg="Starting boot flash...")

        config = self.device_config or self.device_db.get('default')
        if not config:
            QMessageBox.critical(self, "Error", "No device configuration found, cannot proceed.")
            self.log_and_append("Flash failed: Missing device configuration.", level=logging.ERROR)
            self.statusBar.showMessage("Flash failed: No config.", 5000)
            return

        boot_partition = config.get('boot_partition', 'boot') # Default partition name

        # --- Get File Path ---
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Patched Boot Image (.img)", "", "Image Files (*.img);;All Files (*)")
        if not file_path:
            self.log_and_append("File selection cancelled.", status_msg="Flash cancelled.")
            return

        self.log_and_append(f"Selected file: {file_path}", status_msg="File selected.")

        # --- Show Confirmation ---
        reply = QMessageBox.question(self, "Confirm Flash Patched Boot",
                                     f"Are you sure you want to flash '{os.path.basename(file_path)}' to the '{boot_partition}' partition?\n\n"
                                     "WARNING: Flashing an incorrect or unpatched boot image can cause boot loops!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.log_and_append("Patched boot flash cancelled by user.", status_msg="Flash cancelled.")
            return

        self.log_and_append("User confirmed patched boot flash.", level=logging.WARNING)

         # --- Ensure Fastboot Mode ---
        if not self.wait_for_fastboot():
             self.log_and_append("Cannot proceed without device in Fastboot mode.", level=logging.ERROR)
             self.statusBar.showMessage("Flash failed: No Fastboot device.", 5000)
             return

        # --- Send Flash Command ---
        command = f"fastboot flash {boot_partition} \"{file_path}\"" # Use quotes for paths with spaces
        self.log_and_append(f"Sending flash command: {command}", status_msg="Flashing boot...")
        output, success = self.run_command(command, "Patched boot flash command sent.", "Failed to send flash command")

        if success:
            self.log_and_append("Patched boot flash command executed. Check device for status.", status_msg="Flash command sent.")
        else:
            self.log_and_append("Patched boot flash command failed. Check output above for details.", level=logging.ERROR, status_msg="Flash command failed.")

# --- End of added methods ---


if __name__ == "__main__":
    # It's generally best to create the QApplication instance first
    app = QApplication(sys.argv)

    # Apply Material Design theme *after* QApplication is created
    try:
        apply_stylesheet(app, theme='dark_teal.xml')  # You can choose other themes like 'light_blue.xml'
    except Exception as e:
        logging.warning(f"Could not apply qt_material stylesheet: {e}")
        print(f"Warning: Could not apply qt_material stylesheet: {e}")
        print("Ensure 'qt_material' is installed ('pip install qt_material').")
        # Continue without stylesheet if it fails

    window = BootloaderTool()
    window.show()
    sys.exit(app.exec_())