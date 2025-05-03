# main.py
# Goal: Import modules one by one to find silent failure point.
import sys
import logging
print("DEBUG: main.py - Top of file") # Should always print if script starts

# --- Basic Imports ---
try:
    print("DEBUG: main.py - Importing QApplication...")
    from PyQt5.QtWidgets import QApplication
    print("DEBUG: main.py - Imported QApplication.")
except ImportError as e:
    print(f"FATAL ERROR: Failed importing QApplication: {e}")
    sys.exit(1)

# --- Import Constants ---
try:
    print("DEBUG: main.py - Importing constants...")
    # Ensure constants.py doesn't have hidden issues during import
    import constants
    print("DEBUG: main.py - Imported constants module.")
except ImportError as e:
    print(f"FATAL ERROR: Failed importing constants: {e}")
    sys.exit(1)
except Exception as e:
    print(f"FATAL ERROR: Exception during constants import: {e}")
    # Try logging, though it depends on 'constants' import succeeding partially
    try: logging.basicConfig(filename='import_error.log'); logging.exception("Constants import error")
    except: pass
    sys.exit(1)

# --- Setup Logging (Uses constants) ---
# Define function first
def setup_logging():
    print("DEBUG: main.py - Defining setup_logging...")
    try:
        # Access constants after successful import
        log_path = constants.LOG_FILE_PATH
        log_level = constants.LOG_LEVEL_INFO
        log_format = constants.LOG_FORMAT
        print(f"DEBUG: main.py - Logging constants: Path={log_path}, Level={log_level}")

        logging.basicConfig(
            filename=log_path,
            level=log_level,
            format=log_format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        # Add console handler for immediate feedback
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG) # Show debug level on console
        console_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(console_handler)

        logging.info("--- Logging Initialized ---")
        print("DEBUG: main.py - Logging setup complete.")
        return True # Indicate success
    except Exception as e:
        print(f"ERROR: Failed to setup logging: {e}")
        return False # Indicate failure

# Call logging setup AFTER constants import
if not setup_logging():
    print("FATAL ERROR: Logging setup failed. Exiting.")
    sys.exit(1)
logging.info("--- Application Starting ---")

# --- Import Other Custom Modules ---
try:
    print("DEBUG: main.py - Importing ConfigManager...")
    from config_manager import ConfigManager
    print("DEBUG: main.py - Imported ConfigManager.")

    print("DEBUG: main.py - Importing WorkerThread...")
    from worker import WorkerThread
    print("DEBUG: main.py - Imported WorkerThread.")

    print("DEBUG: main.py - Importing DeviceManager...")
    from device_manager import DeviceManager
    print("DEBUG: main.py - Imported DeviceManager.")

    print("DEBUG: main.py - Importing MainWindow...")
    from main_window import MainWindow
    print("DEBUG: main.py - Imported MainWindow.")
except ImportError as e:
    print(f"FATAL ERROR: Failed importing custom module: {e}")
    logging.critical(f"Failed importing custom module: {e}", exc_info=True)
    sys.exit(1)
except Exception as e:
    # Catch other potential errors during module import/parsing
    print(f"FATAL ERROR: Exception during custom module import: {e}")
    logging.critical(f"Exception during custom module import: {e}", exc_info=True)
    sys.exit(1)

# --- Main Execution Block ---
if __name__ == "__main__":
    print("DEBUG: main.py - Running main block.")
    main_window = None
    try:
        print("DEBUG: main.py - Creating QApplication instance...")
        # Ensure QApplication uses constants directly after module import
        app = QApplication(sys.argv)
        print("DEBUG: main.py - QApplication instance created.")

        print("DEBUG: main.py - Applying stylesheet...")
        # Access constant directly after module import
        app.setStyleSheet(constants.WINDOWS_95_STYLE)
        logging.info("Applied Win95 stylesheet.")
        print("DEBUG: main.py - Stylesheet applied.")

        print("DEBUG: main.py - Creating MainWindow instance...")
        # This instantiation will trigger the __init__ chain
        main_window = MainWindow()
        print("DEBUG: main.py - MainWindow instance created.")

        print("DEBUG: main.py - Showing MainWindow...")
        main_window.show()
        logging.info("Main window shown.")
        print("DEBUG: main.py - MainWindow shown.")

        print("DEBUG: main.py - Starting event loop (app.exec_)...")
        exit_code = app.exec_()
        print(f"DEBUG: main.py - Event loop finished (exit_code: {exit_code}).")
        logging.info(f"--- Application Exiting (Code: {exit_code}) ---")
        sys.exit(exit_code)

    except Exception as e:
         print(f"FATAL ERROR in main execution block: {e}")
         logging.critical(f"Fatal error during application execution: {e}", exc_info=True)
         sys.exit(1)
else:
    # This part should not normally be reached when running main.py directly
    print("DEBUG: main.py - Script loaded as module, not executed directly.")