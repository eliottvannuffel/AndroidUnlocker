# test_qt.py
import sys
print("DEBUG: Starting basic PyQt test...")
try:
    # Try importing necessary classes
    print("DEBUG: Importing QApplication, QWidget, QLabel, QVBoxLayout...")
    from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
    print("DEBUG: Imports successful.")

    # --- Application Setup ---
    print("DEBUG: Creating QApplication...")
    app = QApplication(sys.argv)
    print("DEBUG: QApplication created.")

    # --- Window Setup ---
    print("DEBUG: Creating basic QWidget (window)...")
    window = QWidget()
    window.setWindowTitle("Basic PyQt Test")
    window.setGeometry(200, 200, 300, 100) # x, y, width, height
    print("DEBUG: QWidget created.")

    # --- Content Setup ---
    print("DEBUG: Setting layout and label...")
    layout = QVBoxLayout(window)
    label = QLabel("If you see this window, basic PyQt works.", window)
    layout.addWidget(label)
    print("DEBUG: Layout and label added.")

    # --- Show and Run ---
    print("DEBUG: Showing window...")
    window.show()
    print("DEBUG: Window shown.")

    print("DEBUG: Starting event loop (app.exec_)...")
    exit_code = app.exec_()
    print(f"DEBUG: Event loop finished (code: {exit_code}).")
    sys.exit(exit_code)

except Exception as e:
    # Print any error encountered during setup
    print(f"FATAL ERROR during basic PyQt test: {e}")
    import traceback
    print(traceback.format_exc()) # Print full traceback
    # Also try to write to a file
    try:
        with open("test_qt_error.log", "w") as f:
            f.write(f"Error: {e}\n")
            f.write(traceback.format_exc())
    except:
        pass # Ignore errors writing error log
    sys.exit(1) # Exit with error status