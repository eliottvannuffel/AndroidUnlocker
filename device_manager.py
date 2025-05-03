# device_manager.py
import os
import subprocess
import shlex
import logging
import shutil
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot
from worker import WorkerThread
from config_manager import ConfigManager
from constants import (COMMAND_TIMEOUT, SYNC_CMD_TIMEOUT, CREATE_NO_WINDOW,
                       LOG_LEVEL_INFO, LOG_LEVEL_WARNING, LOG_LEVEL_ERROR, LOG_LEVEL_CRITICAL,
                       OUTPUT_TYPE_INFO, OUTPUT_TYPE_STDERR, OUTPUT_TYPE_STDOUT,
                       FLASH_TIMEOUT, SIDELOAD_TIMEOUT, PUSH_PULL_TIMEOUT)


class DeviceManager(QObject):
    """Manages device state, commands, and communication with the UI."""
    # --- Signals for UI updates ---
    device_state_updated = pyqtSignal(str, str, str, str) # mode, serial, manufacturer, model
    log_request = pyqtSignal(str, int, str) # message, level, status_msg
    command_started = pyqtSignal(str) # command string
    command_output_received = pyqtSignal(str, str) # type, line
    command_finished = pyqtSignal(bool, str) # success, command_str
    command_error_occurred = pyqtSignal(str, str) # user_message, command_str
    # Signal if tools aren't found (optional, could just log)
    # tools_check_result = pyqtSignal(bool, bool) # adb_found, fastboot_found

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.current_worker: WorkerThread | None = None
        self.adb_path: str | None = None
        self.fastboot_path: str | None = None

        # Device State
        self.device_mode = 'none'
        self.device_serial_adb = "N/A"
        self.device_serial_fastboot = "N/A"
        self.device_manufacturer = "Unknown"
        self.device_model = "Unknown"
        self.current_config = self.config_manager.get_default()

        # Timer for periodic checks
        self.state_check_timer = QTimer(self)
        self.state_check_timer.timeout.connect(self.check_device_state)

        # Perform initial tool path check
        self.check_tool_paths() # <-- Check paths on initialization

    def check_tool_paths(self):
        """Checks for adb and fastboot executables using shutil.which."""
        self.adb_path = shutil.which("adb")
        self.fastboot_path = shutil.which("fastboot")
        adb_found = bool(self.adb_path)
        fastboot_found = bool(self.fastboot_path)

        if adb_found:
            logging.info(f"ADB found at: {self.adb_path}")
            self.log_request.emit(f"ADB found: {self.adb_path}", LOG_LEVEL_INFO, None)
        else:
            logging.error("ADB executable not found in system PATH.")
            self.log_request.emit("ADB executable not found in system PATH!", LOG_LEVEL_ERROR, "Error: ADB not found!")

        if fastboot_found:
            logging.info(f"Fastboot found at: {self.fastboot_path}")
            self.log_request.emit(f"Fastboot found: {self.fastboot_path}", LOG_LEVEL_INFO, None)
        else:
            logging.error("Fastboot executable not found in system PATH.")
            self.log_request.emit("Fastboot executable not found in system PATH!", LOG_LEVEL_ERROR, "Error: Fastboot not found!")

        # Optionally emit signal if UI needs to react specifically
        # self.tools_check_result.emit(adb_found, fastboot_found)
        return adb_found, fastboot_found

    def _get_tool_command(self, tool_name):
        """Returns the command prefix for adb or fastboot, checking path."""
        if tool_name == "adb":
            if self.adb_path:
                # --- MUST return the raw path ---
                return self.adb_path
            else:
                # Fallback if not found by shutil.which
                return "adb"
        elif tool_name == "fastboot":
            if self.fastboot_path:
                # --- MUST return the raw path ---
                return self.fastboot_path
            else:
                # Fallback if not found by shutil.which
                return "fastboot"
        else:
            # Keep error for unknown tools
            raise ValueError(f"Unknown tool name: {tool_name}")


    def start_monitoring(self, interval_ms=3000):
        """Starts the periodic device state check."""
        if not self.state_check_timer.isActive():
            self.state_check_timer.start(interval_ms)
            logging.info(f"Started device monitoring (interval: {interval_ms}ms)")
            QTimer.singleShot(200, self.check_device_state)

    def stop_monitoring(self):
        """Stops the periodic device state check."""
        if self.state_check_timer.isActive():
            self.state_check_timer.stop()
            logging.info("Stopped device monitoring")

    def is_busy(self):
        """Checks if a command worker is currently running."""
        return self.current_worker is not None and self.current_worker.isRunning()

    def abort_current_command(self):
        """Requests the current worker thread to stop."""
        if self.is_busy():
            self.log_request.emit(f"Attempting to abort: {self.current_worker.command_str}",
                                 LOG_LEVEL_WARNING, "Aborting command...")
            self.current_worker.stop()

    def run_command_sync(self, command, timeout=SYNC_CMD_TIMEOUT):
        """Runs a command synchronously. Use ONLY for quick checks."""
        parts = shlex.split(command)
        if not parts: # Handle empty command string case
            logging.error("run_command_sync called with empty command string.")
            return "", False
        tool = parts[0]
        cmd_list = parts # Default to original split list

        try:
            # Replace tool name with full path if known and applicable
            if tool in ["adb", "fastboot"]:
                 tool_path = self._get_tool_command(tool) # Get path or name
                 cmd_list[0] = tool_path # Replace item in list

            # --- ADDED/MODIFIED DEBUGGING ---
            current_cwd = os.getcwd()
            logging.debug(f"run_command_sync: Attempting to run. Original='{command}', CWD='{current_cwd}'")
            logging.debug(f"run_command_sync: Prepared command list for subprocess.run: {cmd_list}")
            # You can uncomment the next line if needed, but it's very verbose
            # logging.debug(f"run_command_sync: Current PATH environment: {os.environ.get('PATH', 'Not Set')}")
            # --- END DEBUGGING ---

            process = subprocess.run(
                 cmd_list, # Pass list of arguments
                 capture_output=True,
                 text=True,
                 encoding='utf-8',
                 errors='replace',
                 timeout=timeout,
                 check=False,
                 startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=subprocess.SW_HIDE) if CREATE_NO_WINDOW else None
             )

            # Log success/failure clearly
            if process.returncode == 0:
                 logging.debug(f"Sync command success: {cmd_list}")
            # Log failure, but don't spam warnings for 'devices' command if no device is found (which often returns non-zero)
            elif not (command.endswith(" devices")):
                 logging.warning(f"Sync command failed (Code {process.returncode}): {cmd_list}\nStderr: {process.stderr.strip()}")
            elif process.returncode != 0 and command.endswith(" devices"):
                 logging.debug(f"Sync command '{command}' returned code {process.returncode} (likely no device/expected). Stderr: {process.stderr.strip()}")


            return process.stdout.strip(), process.returncode == 0
        except FileNotFoundError:
             # Log details about what failed - critically important now
             logging.critical(f"Sync command FileNotFoundError: Failed to execute {cmd_list} (Original command: '{command}')", exc_info=False)
             self.log_request.emit(f"Sync Error: Executable not found for '{cmd_list[0]}'. Check PATH/permissions.", LOG_LEVEL_CRITICAL, "Error: Tool not found!")
             return "", False
        except subprocess.TimeoutExpired:
             logging.warning(f"Sync command timed out: {cmd_list} (Original command: '{command}')")
             return "", False
        except Exception as e:
             # Log any other unexpected exceptions during subprocess execution
             logging.error(f"Error running sync command {cmd_list} (Original command: '{command}'): {e}", exc_info=True)
             return "", False

    # --- Device State and Detection ---
    def check_device_state(self):
        """Checks for connected devices and updates internal state."""
        if self.is_busy():
            return

        adb_output, adb_success = self.run_command_sync("adb devices")
        fastboot_output, fastboot_success = self.run_command_sync("fastboot devices")

        new_mode = 'none'
        serial_adb = "N/A"
        serial_fastboot = "N/A"
        found_device = False

        if adb_success:
            lines = adb_output.strip().splitlines()
            if len(lines) > 1:
                for line in lines[1:]:
                    parts = line.split('\t')
                    if len(parts) == 2:
                        serial, status = parts[0].strip(), parts[1].strip()
                        if status == 'device':
                            new_mode, serial_adb, found_device = 'adb', serial, True; break
                        elif status == 'sideload':
                            new_mode, serial_adb, found_device = 'sideload', serial, True; break

        if not found_device and fastboot_success:
            lines = fastboot_output.strip().splitlines()
            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[1].lower() == 'fastboot':
                    new_mode, serial_fastboot, found_device = 'fastboot', parts[0].strip(), True; break

        state_changed = (new_mode != self.device_mode or
                         serial_adb != self.device_serial_adb or
                         serial_fastboot != self.device_serial_fastboot)

        if state_changed:
            self.device_mode = new_mode
            self.device_serial_adb = serial_adb
            self.device_serial_fastboot = serial_fastboot
            current_serial = serial_adb if new_mode in ('adb', 'sideload') else serial_fastboot if new_mode == 'fastboot' else 'N/A'

            if new_mode == 'none' or (new_mode == 'fastboot' and self.device_manufacturer != "Unknown") or \
               (new_mode in ('adb', 'sideload') and self.device_manufacturer == "Unknown (Fastboot)"):
                 self.device_manufacturer = "Unknown"
                 self.device_model = "Unknown"
                 self.current_config = self.config_manager.get_device_config()
                 if new_mode == 'none':
                      self.log_request.emit("Device disconnected.", LOG_LEVEL_INFO, "Device disconnected.")

            self.device_state_updated.emit(self.device_mode, current_serial, self.device_manufacturer, self.device_model)
            logging.debug(f"Device state updated: Mode={self.device_mode}, Serial={current_serial}")

            if new_mode != 'none' and self.device_manufacturer == "Unknown":
                 self.log_request.emit(f"Device connected ({new_mode}). Auto-detecting...", LOG_LEVEL_INFO, "Detecting device...")
                 QTimer.singleShot(200, self.detect_device_details)

    def detect_device_details(self):
        """Attempts to detect manufacturer and model."""
        if self.is_busy() or self.device_mode == 'none':
            return

        self.log_request.emit("Detecting device details...", LOG_LEVEL_INFO, "Detecting...")
        detected_mfr = None
        detected_model = None
        detected_serial = "N/A"
        config_source = "Default"

        try:
            if self.device_mode in ('adb', 'sideload'):
                detected_serial = self.device_serial_adb
                mfr_output, mfr_ok = self.run_command_sync("adb shell getprop ro.product.manufacturer")
                model_output, model_ok = self.run_command_sync("adb shell getprop ro.product.model")
                detected_mfr = mfr_output.strip() if mfr_ok and mfr_output else None
                detected_model = model_output.strip() if model_ok and model_output else None
            elif self.device_mode == 'fastboot':
                detected_serial = self.device_serial_fastboot
                product_output, prod_ok = self.run_command_sync("fastboot getvar product")
                if prod_ok and product_output and ':' in product_output:
                    detected_model = product_output.split(':', 1)[1].strip()
                detected_mfr = "Unknown (Fastboot)"

            if detected_mfr or detected_model:
                self.device_manufacturer = detected_mfr or "Unknown"
                self.device_model = detected_model or "Unknown"
                self.current_config = self.config_manager.get_device_config(self.device_manufacturer, self.device_model)
                if self.current_config != self.config_manager.get_default():
                    config_source = "YAML"
                    if not detected_model and detected_mfr != "Unknown (Fastboot)":
                         config_source += " (Mfr Match)"
                log_msg = f"Detected: {self.device_manufacturer} {self.device_model} ({self.device_mode})"
                status_msg = f"Detected: {self.device_manufacturer} {self.device_model}"
                self.log_request.emit(log_msg, LOG_LEVEL_INFO, status_msg)
                self.log_request.emit(f"Using configuration: {config_source}", LOG_LEVEL_INFO, status_msg)
                notes = self.current_config.get('notes')
                if notes:
                     self.log_request.emit(f"Notes: {notes}", LOG_LEVEL_INFO, None)
            else:
                 self.device_manufacturer = "Unknown"
                 self.device_model = "Unknown"
                 self.current_config = self.config_manager.get_default()
                 self.log_request.emit("Could not detect details, using defaults.", LOG_LEVEL_WARNING, "Detection failed")

            self.device_state_updated.emit(self.device_mode, detected_serial, self.device_manufacturer, self.device_model)

            # Run background info commands
            if self.device_mode == 'adb':
                 self._start_command(self._get_tool_command("adb") + " shell getprop", COMMAND_TIMEOUT, is_background_info=True)
            elif self.device_mode == 'fastboot':
                  self._start_command(self._get_tool_command("fastboot") + " getvar all", COMMAND_TIMEOUT, is_background_info=True)
        except Exception as e:
             self.log_request.emit(f"Error during detection: {e}", LOG_LEVEL_CRITICAL, "Detection error!")
             logging.exception("Unhandled exception in detect_device_details")
             self.device_manufacturer = "Unknown"
             self.device_model = "Unknown"
             self.current_config = self.config_manager.get_default()
             self.device_state_updated.emit(self.device_mode, detected_serial, self.device_manufacturer, self.device_model)

    # --- Command Execution ---

    # CORRECTED Method Definition
    def _start_command(self, command_str, timeout, success_msg=None, error_prefix=None, status_during=None, is_background_info=False):
        """Internal method to create and start a WorkerThread with status updates."""
        if self.is_busy():
            if not is_background_info:
                self.log_request.emit("Busy: Another command is running.", LOG_LEVEL_WARNING, "Busy")
                return False
            else:
                logging.debug(f"Skipping background command due to busy state: {command_str}")
                return False

        parts = shlex.split(command_str)
        tool = parts[0]
        command_to_log = command_str # Default to original
        if tool in ["adb", "fastboot"]:
             try:
                 # Attempt to rebuild for logging, prefer passing original to WorkerThread
                 parts_with_path = parts[:] # Copy list
                 parts_with_path[0] = self._get_tool_command(tool)
                 command_to_log = " ".join(parts_with_path) # Simple join for logging
             except Exception:
                 pass # Ignore errors during rebuild for logging

        # CORRECTED: Use status_during here
        status_msg = status_during if status_during else f"Starting: {command_to_log.split(' ')[0]}..."
        if is_background_info:
            status_msg = None # No status for background info commands

        self.log_request.emit(f"Running: {command_to_log}", LOG_LEVEL_INFO, status_msg)

        self.current_worker = WorkerThread(command_str, timeout) # Pass original command string

        # Store context
        self.current_worker.success_msg = success_msg
        self.current_worker.error_prefix = error_prefix
        self.current_worker.is_background_info = is_background_info
        # CORRECTED: Store status_during here
        self.current_worker.status_during = status_during

        # Connect signals
        self.current_worker.started.connect(self._on_worker_started)
        self.current_worker.output.connect(self._on_worker_output)
        self.current_worker.error.connect(self._on_worker_error)
        self.current_worker.finished.connect(self._on_worker_finished)

        self.current_worker.start()
        self.command_started.emit(command_str)
        return True

    @pyqtSlot(str)
    def _on_worker_started(self, command_str):
        # CORRECTED: Use status_during here
        worker = self.sender()
        status_during = getattr(worker, 'status_during', None)
        if status_during:
             self.log_request.emit("", LOG_LEVEL_INFO, status_during)
        logging.debug(f"Worker started for: {command_str}")

    @pyqtSlot(str, str)
    def _on_worker_output(self, output_type, line):
        self.command_output_received.emit(output_type, line)

    @pyqtSlot(str, str)
    def _on_worker_error(self, user_message, command_str):
        self.command_error_occurred.emit(user_message, command_str)

    @pyqtSlot(int, str, str, str)
    def _on_worker_finished(self, returncode, stdout, stderr, command_sent):
        worker = self.sender()
        if worker != self.current_worker:
             logging.warning("Finished signal received from unexpected worker.")
             return

        success = returncode == 0
        success_msg = getattr(worker, 'success_msg', f"Command '{command_sent.split(' ')[0]}' finished.")
        error_prefix = getattr(worker, 'error_prefix', f"Command '{command_sent.split(' ')[0]}' failed")
        is_background = getattr(worker, 'is_background_info', False)

        status_msg = ""
        if not is_background:
            final_status = status_msg # Default if no specific message found below
            if success:
                status_msg = success_msg
                self.log_request.emit(f"Success: {command_sent}", LOG_LEVEL_INFO, status_msg)
                # Determine more specific final status
                if "unlock" in command_sent: final_status = "Unlock sent. Check device!"
                elif "lock" in command_sent: final_status = "Lock sent. Check device!"
                elif "sideload" in command_sent: final_status = "Sideload finished/aborted."
                elif "flash" in command_sent: final_status = "Flash operation finished."
                elif "boot" in command_sent: final_status = "Boot command finished. Check device."
                elif "push" in command_sent: final_status = "Push finished."
                elif "pull" in command_sent: final_status = "Pull finished."
                else: final_status = status_msg # Default success message

                if final_status != status_msg:
                     self.log_request.emit(final_status, LOG_LEVEL_WARNING if "Check device" in final_status else LOG_LEVEL_INFO, None)
                self.log_request.emit("", LOG_LEVEL_INFO, final_status) # Update status bar
            else:
                status_msg = error_prefix
                self.log_request.emit(f"Failed: {command_sent} (Code: {returncode})", LOG_LEVEL_ERROR, status_msg)
        else:
             logging.debug(f"Background command finished: {command_sent} (Code: {returncode})")

        self.current_worker = None
        self.command_finished.emit(success, command_sent)

        if not is_background:
            QTimer.singleShot(500, self.check_device_state)

    # --- Public Methods for Core Actions ---

    def get_config_value(self, key, default=None):
        return self.current_config.get(key, default)

    def execute_unlock(self):
        command_template = self.get_config_value('unlock_command', 'fastboot oem unlock')
        command = f"fastboot {command_template.split(' ', 1)[1]}"
        # CORRECTED Call
        self._start_command(command, COMMAND_TIMEOUT,
                            success_msg="Unlock complete.", error_prefix="Unlock failed",
                            status_during="Sending unlock command...")

    def execute_lock(self):
        command_template = self.get_config_value('lock_command', 'fastboot oem lock')
        command = f"fastboot {command_template.split(' ', 1)[1]}"
        # CORRECTED Call
        self._start_command(command, COMMAND_TIMEOUT,
                            success_msg="Lock complete.", error_prefix="Lock failed",
                            status_during="Sending lock command...")

    def execute_flash(self, partition_type, file_path):
        partition_name = self.get_config_value(f'{partition_type}_partition', partition_type)
        command = f'fastboot flash {shlex.quote(partition_name)} "{file_path}"'
        # CORRECTED Call
        self._start_command(command, FLASH_TIMEOUT,
                            success_msg=f"{partition_type.capitalize()} flash finished.",
                            error_prefix=f"Flash {partition_type} failed",
                            status_during=f"Flashing {partition_name}...")

    def execute_boot_image(self, file_path):
        command = f'fastboot boot "{file_path}"'
        # CORRECTED Call
        self._start_command(command, COMMAND_TIMEOUT,
                            success_msg="Boot command finished.",
                            error_prefix="Boot image failed",
                            status_during="Booting image (no flash)...")

    def execute_sideload(self, file_path):
        command = f'adb sideload "{file_path}"'
        # CORRECTED Call
        self._start_command(command, SIDELOAD_TIMEOUT,
                            success_msg="ADB Sideload finished/aborted.",
                            error_prefix="Sideload failed",
                            status_during="Sideloading ZIP...")

    def execute_push(self, local_path, device_path):
        command = f'adb push "{local_path}" "{device_path}"'
        # CORRECTED Call
        self._start_command(command, PUSH_PULL_TIMEOUT,
                            success_msg="Push finished.",
                            error_prefix="Push failed",
                            status_during="Pushing file...")

    def execute_pull(self, device_path, local_path):
        command = f'adb pull "{device_path}" "{local_path}"'
        # CORRECTED Call
        self._start_command(command, PUSH_PULL_TIMEOUT,
                             success_msg="Pull finished.",
                             error_prefix="Pull failed",
                             status_during="Pulling file...")

    def execute_reboot(self, target):
        command = None
        action_name = f"Reboot {target.capitalize()}"
        # CORRECTED Variable Name
        status_during = f"Rebooting to {target}..."
        if self.device_mode == 'adb':
             cmd_key = f'adb_reboot_{target}_command'
             default = f'adb reboot {target}' if target != 'system' else 'adb reboot'
             command = self.get_config_value(cmd_key, default)
        elif self.device_mode == 'fastboot' and target == 'system':
             cmd_key = 'fastboot_reboot_command'
             default = 'fastboot reboot'
             command = self.get_config_value(cmd_key, default)

        if command:
            # CORRECTED Call
            self._start_command(command, COMMAND_TIMEOUT,
                                success_msg=f"{action_name} command sent.",
                                error_prefix=f"{action_name} failed",
                                status_during=status_during)
            return True
        else:
            allowed_modes = "ADB" + (" or Fastboot" if target == 'system' else "")
            self.log_request.emit(f"Cannot reboot to {target} from {self.device_mode} mode.",
                                  LOG_LEVEL_ERROR, f"Wrong mode for reboot {target}")
            return False