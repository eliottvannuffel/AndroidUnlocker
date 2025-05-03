# Android Bootloader Tool (Win95 Style)

A simple Python desktop application with a retro Windows 95 style GUI for performing common Android Debug Bridge (ADB) and Fastboot tasks related to bootloader management, flashing images, and sideloading.

---

**⚠️ DISCLAIMER & WARNINGS ⚠️**

* **DATA LOSS:** Operations like **unlocking** or **locking** the bootloader WILL typically **erase all user data** on your device (perform a factory reset). Always back up your important data first!
* **BRICKING RISK:** Flashing incorrect images (boot, recovery, etc.) or performing operations on the wrong partition can potentially **brick your device**, rendering it unusable. Ensure you are using files specifically designed for your device model and variant.
* **WARRANTY:** Unlocking the bootloader may void your device's warranty.
* **USE AT YOUR OWN RISK:** You assume all responsibility for any damage or data loss that may occur to your device as a result of using this tool. The developers are not liable for any issues. Proceed with caution and understanding.

---

## Features

* **Device Detection:** Detects connected devices in ADB, Fastboot, and Sideload modes. Displays basic device information (Manufacturer, Model, Serial - best effort via ADB).
* **Bootloader Management:**
    * Unlock Bootloader (via Fastboot - Wipes Data!)
    * Lock Bootloader (via Fastboot - Use with caution, ensure stock firmware!)
* **Flashing (via Fastboot):**
    * Flash Recovery Image (`.img`)
    * Flash Boot Image (`.img`)
* **Booting (via Fastboot):**
    * Boot Recovery/Boot Image (`.img`) without permanently flashing it.
* **Sideloading (via ADB):**
    * Sideload ZIP files (e.g., ROMs, OTA updates) from Recovery mode.
* **File Transfer (via ADB):**
    * Push files from PC to device.
    * Pull files from device to PC.
* **Reboot Options:**
    * Reboot to System (from ADB or Fastboot)
    * Reboot to Recovery (from ADB)
    * Reboot to Bootloader/Fastboot (from ADB)
* **Configuration:** Uses an optional `devices.yaml` for device-specific commands and partition names.
* **Logging:** Logs operations and errors to `bootloader_tool_win95.log`.
* **UI Style:** Intentionally styled to resemble Windows 95 using PyQt5.

---

## Requirements

1.  **Python:** Python 3 (tested with 3.8+, might work with earlier 3.x versions).
2.  **Python Libraries:** PyQt5 and PyYAML. Install using pip:
    ```bash
    pip install -r requirements.txt
    # Or: pip install PyQt5 PyYAML
    ```
3.  **ADB and Fastboot:**
    * These tools are **NOT** included with this application.
    * You need to download the **Android SDK Platform Tools** from the official Android Developers website: [https://developer.android.com/tools/releases/platform-tools](https://developer.android.com/tools/releases/platform-tools)
    * Extract the downloaded zip file.
    * **Crucially:** You **must add the directory** containing `adb` (or `adb.exe`) and `fastboot` (or `fastboot.exe`) **to your system's PATH environment variable** so this application (and your terminal) can find them. The application attempts to detect them on startup.

---

## Installation

1.  **Clone or Download:**
    * Clone the repository: `git clone <repository-url>`
    * Or download the source code ZIP and extract it.
2.  **Install Dependencies:**
    * Navigate to the project directory in your terminal.
    * Install the required Python libraries:
        ```bash
        pip install -r requirements.txt
        ```
3.  **Install ADB/Fastboot:** Ensure ADB and Fastboot are installed and added to your system PATH (see Requirements section).

---

## Configuration (`devices.yaml`)

* This tool can use a `devices.yaml` file (placed in the same directory as `main.py`) to specify non-standard commands or partition names for particular devices.
* If the file is missing or a specific device isn't listed, default commands and partition names (`boot`, `recovery`) are used.
* The matching is case-insensitive. Keys should be lowercase `manufacturer model` or just `manufacturer`.

**Example `devices.yaml`:**

```yaml
# Default settings can be overridden here if needed under 'default:' key
# default:
#   notes: "Overridden default notes."

google pixel 6:
  unlock_command: "fastboot flashing unlock"
  lock_command: "fastboot flashing lock"
  # recovery_partition: recovery # Default is usually fine
  notes: "Pixel 6 uses 'flashing' commands."

samsung: # Match any Samsung device if model doesn't match specifically
  # Samsung often requires Odin, standard commands might fail
  unlock_command: "" # Indicate standard command won't work
  lock_command: ""
  adb_reboot_bootloader_command: "adb reboot download" # Use download mode
  notes: "Samsung devices often need Odin/Download mode. Standard fastboot commands may not apply."

```

---

## Usage

1.  **Connect Device:** Connect your Android device to your computer via USB.
2.  **Enable USB Debugging:** For ADB commands, ensure USB Debugging is enabled in Developer Options on your device. You may need to authorize your computer.
3.  **Boot into Correct Mode:**
    * For ADB operations (push, pull, reboot commands): Device should be booted normally into Android with USB Debugging enabled.
    * For Fastboot operations (unlock, lock, flash, boot): Device needs to be booted into its Bootloader/Fastboot mode (methods vary by device - often involves holding Volume Down + Power).
    * For Sideload: Device needs to be booted into Recovery mode, and ADB Sideload mode must be activated from the recovery menu.
4.  **Run the Application:**
    * Open your terminal in the project directory.
    * Execute:
        ```bash
        python3 main.py
        ```
5.  **Use the GUI:** Select the desired actions. Read all warnings carefully before proceeding with potentially destructive operations like unlocking or flashing. Use the "Detect Device" button first.

---

## Logging

* All operations and significant errors are logged to `bootloader_tool_win95.log` in the application's directory. Check this file for detailed information if you encounter issues.