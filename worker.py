# worker.py
import subprocess
import shlex
import sys
import logging
from PyQt5.QtCore import QThread, pyqtSignal
from constants import CREATE_NO_WINDOW # Import constant for subprocess flag

class WorkerThread(QThread):
    """Runs a command in a separate thread and emits signals."""
    # Signals to communicate with the main thread/manager
    started = pyqtSignal(str) # command_str
    finished = pyqtSignal(int, str, str, str) # returncode, stdout, stderr, command_sent
    output = pyqtSignal(str, str) # type ('stdout' or 'stderr'), line
    error = pyqtSignal(str, str) # user_message, command_str

    def __init__(self, command, timeout):
        super().__init__()
        self.command_str = command
        self.timeout = timeout
        self.process = None # Keep reference to the process

    def run(self):
        self.started.emit(self.command_str)
        logging.info(f"Worker executing: {self.command_str}")
        stdout_lines = []
        stderr_lines = []

        try:
            self.process = subprocess.Popen(
                shlex.split(self.command_str),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1, # Line buffered
                creationflags=CREATE_NO_WINDOW
            )

            # Poll process and read output line by line
            while True:
                stdout_line = self.process.stdout.readline()
                stderr_line = self.process.stderr.readline()

                if stdout_line:
                    stripped_line = stdout_line.strip()
                    if stripped_line:
                        self.output.emit('stdout', stripped_line)
                        stdout_lines.append(stdout_line)

                if stderr_line:
                    stripped_line = stderr_line.strip()
                    if stripped_line:
                        self.output.emit('stderr', stripped_line)
                        stderr_lines.append(stderr_line)

                # Check if process has terminated and no more output is available
                process_poll = self.process.poll()
                if process_poll is not None and not stdout_line and not stderr_line:
                    break

                self.msleep(50) # Prevent high CPU usage

            # Ensure process is finished and get final code (might block briefly if not finished)
            returncode = self.process.wait(timeout=self.timeout)

            full_stdout = "".join(stdout_lines).strip()
            full_stderr = "".join(stderr_lines).strip()
            logging.info(f"Worker finished '{self.command_str}' with code {returncode}")
            self.finished.emit(returncode, full_stdout, full_stderr, self.command_str)

        except FileNotFoundError:
            msg = f"Error: Command executable ('{shlex.split(self.command_str)[0]}') not found. Check PATH."
            logging.error(msg, exc_info=False) # No need for full traceback here
            self.error.emit(msg, self.command_str)
            self.finished.emit(-1, "", "", self.command_str) # Indicate failure
        except subprocess.TimeoutExpired:
            msg = f"Command '{self.command_str}' timed out after {self.timeout} seconds."
            logging.error(msg, exc_info=False)
            self.error.emit(msg, self.command_str)
            self._terminate_process()
            self.finished.emit(-1, "", "", self.command_str) # Indicate failure
        except Exception as e:
            msg = f"Unexpected worker error running '{self.command_str}': {e}"
            logging.error(msg, exc_info=True)
            self.error.emit(msg, self.command_str)
            self.finished.emit(-1, "", "", self.command_str) # Indicate failure
        finally:
             self.process = None # Clear process reference

    def _terminate_process(self):
        """Attempts to terminate the running process."""
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2) # Give it time to terminate
                logging.warning(f"Terminated process for command: {self.command_str}")
            except Exception as term_err:
                 logging.error(f"Error during process termination: {term_err}")
                 try:
                      self.process.kill() # Force kill as last resort
                      logging.warning(f"Killed process for command: {self.command_str}")
                 except Exception as kill_err:
                      logging.error(f"Error killing process: {kill_err}")

    def stop(self):
        """Requests termination of the running process."""
        logging.warning(f"Termination requested for worker: {self.command_str}")
        self._terminate_process()