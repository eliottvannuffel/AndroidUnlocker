# config_manager.py
import yaml
import os
import logging
from constants import YAML_FILE_PATH

class ConfigManager:
    def __init__(self):
        self.device_db = {}
        self._load_device_database()

    def _get_default_config(self):
        # Define a robust default configuration
        return {
            'unlock_command': "fastboot oem unlock",
            'lock_command': "fastboot oem lock",
            'recovery_partition': "recovery",
            'boot_partition': "boot",
            'unlock_warning': "Unlocking the bootloader will wipe all user data (factory reset) and may void your warranty! Proceed with caution.",
            'lock_warning': "Locking the bootloader might wipe all user data. Ensure you are on stock firmware before locking.",
            'adb_reboot_bootloader_command': "adb reboot bootloader",
            'adb_reboot_recovery_command': "adb reboot recovery",
            'adb_reboot_system_command': "adb reboot",
            'fastboot_reboot_command': "fastboot reboot",
            'notes': 'Default configuration. Device-specific commands may differ.'
        }

    def _load_device_database(self):
        """Loads the device database from the YAML file."""
        default_config = self._get_default_config()
        self.device_db['default'] = default_config  # Ensure default is always present

        loaded_db = {}
        try:
            if os.path.exists(YAML_FILE_PATH):
                with open(YAML_FILE_PATH, 'r', encoding='utf-8') as f:
                    try:
                        loaded_db = yaml.safe_load(f)
                        if not isinstance(loaded_db, dict):
                            logging.error(f"Invalid YAML structure in {YAML_FILE_PATH}: Expected a dictionary. Using default only.")
                            loaded_db = {} # Reset to avoid processing invalid structure
                        else:
                             logging.info(f"Successfully loaded YAML file: {YAML_FILE_PATH}")

                    except yaml.YAMLError as e:
                        logging.error(f"Error parsing YAML file {YAML_FILE_PATH}: {e}", exc_info=True)
                        # Keep device_db as default only
                        return # Stop processing here
                    except Exception as e:
                        logging.error(f"Unexpected error reading {YAML_FILE_PATH}: {e}", exc_info=True)
                        return # Stop processing here
            else:
                logging.warning(f"{YAML_FILE_PATH} not found. Using default commands only.")
                # No need to return, defaults are already set

            # Process the loaded dictionary (if valid)
            for key, value in loaded_db.items():
                 lower_key = key.lower() # Use lowercase keys for matching
                 if lower_key == 'default': # Allow overriding defaults
                      if isinstance(value, dict):
                           # Merge loaded defaults with hardcoded defaults
                           merged_default = default_config.copy()
                           merged_default.update(value)
                           self.device_db['default'] = merged_default
                      else:
                           logging.warning(f"Ignoring invalid 'default' entry in YAML (not a dictionary).")
                 elif isinstance(value, dict):
                      # Ensure all default keys are present in this device entry
                      device_entry = default_config.copy()
                      device_entry.update(value) # Overwrite with specific values
                      self.device_db[lower_key] = device_entry
                 else:
                      logging.warning(f"Skipping invalid entry '{key}' in YAML (not a dictionary).")

        except Exception as e:
            logging.critical(f"Critical error during database loading processing: {e}", exc_info=True)
            # Fallback to default is already handled by initialization


    def get_device_config(self, manufacturer=None, model=None):
        """Finds the device configuration (case-insensitive). Returns default if no match."""
        default_conf = self.device_db.get('default', self._get_default_config()) # Failsafe

        if not manufacturer: # Cannot match without manufacturer
            return default_conf

        mfr_lower = manufacturer.lower()

        # Prioritize exact match (manufacturer + model)
        if model:
            model_lower = model.lower()
            exact_key = f"{mfr_lower} {model_lower}"
            if exact_key in self.device_db:
                logging.info(f"Config: Found exact match for '{exact_key}'")
                # Return a copy merged with defaults to ensure all keys are present
                # (Merging happened during load, so just return the stored dict)
                return self.device_db[exact_key]

        # Fallback to manufacturer match
        if mfr_lower in self.device_db:
            logging.info(f"Config: Found manufacturer match for '{mfr_lower}'")
            return self.device_db[mfr_lower]

        logging.warning(f"Config: No specific config found for Mfr='{manufacturer}', Model='{model}'. Using default.")
        return default_conf

    def get_default(self):
        """Returns the default configuration dictionary."""
        return self.device_db.get('default', self._get_default_config())