# home.py
#
# Job:
# ----
# This module defines the HomeMenu class, which serves as the entry screen (main menu)
# for the Family Tree Creator application. It provides users with three clear actions:
# launching the graphical tree editor, opening the options configurations menu, or exiting.
#
# How it works:
# -------------
# 1. Layout management: Uses a centered vertical layout (QVBoxLayout) and horizontal layouts
#    (QHBoxLayout) with elastic spacing (stretch) to place buttons cleanly in the window center.
# 2. Window visibility flow: When opening the Editor or Options window, the menu hides itself
#    (`self.hide()`) and wires the child window's `closed` signal to trigger showing the menu
#    again (`self.show()`), ensuring a single active window at a time.
# 3. Dynamic styling: Integrates with options.py settings to fetch user styling configurations.
#    Reacts to resize events (`resizeEvent`) to scale title and button labels proportionally.

import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import options
import editor

class HomeMenu(QMainWindow):
    """
    Main entry point menu window. Houses buttons to start editing, view options, or exit.
    """

    def __init__(self):
        """
        Job:
        ----
        Initializes the home screen menu, sets up layout geometry, and registers buttons.
        """
        super().__init__()

        self.setWindowTitle("Family Tree Creator")
        self.resize(800, 600)

        # Main central container
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()

        # --- Title ---
        self.title_label = QLabel("Family Tree Creator")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout.addStretch(1) # Add flexible vertical spacing above the title
        main_layout.addWidget(self.title_label)
        main_layout.addStretch(1) # Add flexible vertical spacing below the title

        # --- Buttons Configuration ---
        # Map button texts to target methods
        button_actions = {
            "Tree Editor": self.create_new_tree,
            "Options": self.open_options,
            "Exit": self.exit_program
        }

        self.ui_buttons = [] # Store buttons list to allow batch updates during resize events

        for name, function in button_actions.items():
            btn = QPushButton(name)
            # Instruct buttons to expand horizontally and vertically to fill spacing
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.ui_buttons.append(btn)

            # Row layout to keep buttons centered with margins on both sides
            row_layout = QHBoxLayout()
            row_layout.addStretch(1)
            row_layout.addWidget(btn, stretch=2)
            row_layout.addStretch(1)

            main_layout.addLayout(row_layout)
            btn.clicked.connect(function)

        main_layout.addStretch(2) # Spacing below the button stack
        central_widget.setLayout(main_layout)

        self.setMinimumSize(640, 480)

        # Fetch and apply user settings (Light/Dark themes)
        self.apply_settings()

    def apply_settings(self):
        """
        Job:
        ----
        Applies stylesheet styling constraints defined in options.py (e.g. Dark/Light mode).
        """
        options.OptionsMenu.apply_theme_to_window(self)

    def resizeEvent(self, event):
        """
        Job:
        ----
        Reacts to window resize actions, recalculating font sizes dynamically to keep
        labels readable.

        How it does it:
        --------------
        - Reads font size setting from settings.json.
        - Calculates the minimum dimension of the window (width vs height) to use as scale factor.
        - Scales title label (10% of window size) and buttons (5% of window size) proportionally.
        """
        super().resizeEvent(event)

        settings = options.OptionsMenu.get_settings()
        base_font_size = settings.get('font_size', 12)

        # Determine the smaller dimension to scale font sizes appropriately
        window_size = min(self.width(), self.height())

        dynamic_title_size = max(base_font_size + 6, int(window_size * 0.1))
        dynamic_button_size = max(base_font_size, int(window_size * 0.05))

        self.title_label.setFont(QFont("Arial", dynamic_title_size, QFont.Weight.Bold))

        button_font = QFont("Arial", dynamic_button_size)
        for btn in self.ui_buttons:
            btn.setFont(button_font)

    def create_new_tree(self):
        """
        Job:
        ----
        Click handler for "Tree Editor". Navigates to the editor screen.
        """
        self.open_editor()

    def open_editor(self):
        """
        Job:
        ----
        Launches the TreeEditor window, hides the home menu, and registers a callback
        to restore the menu when the editor window is closed.
        """
        self.editor_window = editor.TreeEditor(self)
        # Connect editor window close event to showing this home menu again
        self.editor_window.closed.connect(self.show)
        self.hide()
        self.editor_window.show()

    def open_options(self):
        """
        Job:
        ----
        Launches the OptionsMenu settings window, hides the home menu, and registers a callback
        to restore the menu and reapply settings (e.g. theme changes) when the options window closes.
        """
        print("Action: Opening options menu...")
        self.options_window = options.OptionsMenu(self)
        self.options_window.closed.connect(self.show_and_refresh)
        self.hide()
        self.options_window.show()

    def show_and_refresh(self):
        """
        Job:
        ----
        Restores the main menu visibility and applies any updated settings (like themes).
        """
        self.show()
        self.apply_settings()

    def exit_program(self):
        """
        Job:
        ----
        Exits the application. Prompts for confirmation if 'confirm_exit' setting is enabled.
        """
        settings = options.OptionsMenu.get_settings()
        if settings.get('confirm_exit', True):
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, 'Confirm Exit',
                "Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        print("Action: Closing the application.")
        self.close()

if __name__ == "__main__":
    # Launch main application thread
    app = QApplication(sys.argv)
    window = HomeMenu()
    window.show()
    sys.exit(app.exec())