# home.py
# This module defines the starting screen (main menu) for the Family Tree Creator application.
# Non-programmers: think of this as the first page with 3 big buttons to start, configure, or quit.

import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import options
import editor

class HomeMenu(QMainWindow):
    """Top-level application window with main menu choices."""

    def __init__(self):
        super().__init__()

        # Window title and size
        self.setWindowTitle("Family Tree Creator")
        self.resize(800, 600)

        # Create a main container and vertical layout.
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()

        # --- Title ---
        self.title_label = QLabel("Family Tree Creator")
        # We don't set a fixed font size here; resizeEvent controls font size dynamically.
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout.addStretch(1)
        main_layout.addWidget(self.title_label)
        main_layout.addStretch(1)

        # --- Buttons ---
        # Map visible button text to the method that should run when clicked.
        button_actions = {
            "Tree Editor": self.create_new_tree,
            "Options": self.open_options,
            "Exit": self.exit_program
        }

        # Keep a list of buttons so we can resize fonts later.
        self.ui_buttons = []

        for name, function in button_actions.items():
            btn = QPushButton(name)
            # Make the buttons expand with the window.
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.ui_buttons.append(btn)

            # A centered row for each button (left gap, button, right gap).
            row_layout = QHBoxLayout()
            row_layout.addStretch(1)
            row_layout.addWidget(btn, stretch=2)
            row_layout.addStretch(1)

            main_layout.addLayout(row_layout)
            btn.clicked.connect(function)

        main_layout.addStretch(2)
        central_widget.setLayout(main_layout)

        self.setMinimumSize(640, 480)

        # Apply settings (theme and font)
        self.apply_settings()

    def apply_settings(self):
        """Apply current settings to this window."""
        options.OptionsMenu.apply_theme_to_window(self)

    def resizeEvent(self, event):
        """Automatically adjusts text size when user resizes the main window."""
        super().resizeEvent(event)

        settings = options.OptionsMenu.get_settings()
        base_font_size = settings.get('font_size', 12)

        # Use the smaller of width and height to choose font sizes.
        window_size = min(self.width(), self.height())

        dynamic_title_size = max(base_font_size + 6, int(window_size * 0.1))
        dynamic_button_size = max(base_font_size, int(window_size * 0.05))

        self.title_label.setFont(QFont("Arial", dynamic_title_size, QFont.Weight.Bold))

        button_font = QFont("Arial", dynamic_button_size)
        for btn in self.ui_buttons:
            btn.setFont(button_font)

    def create_new_tree(self):
        """Button action: open the tree editor."""
        self.open_editor()

    def open_editor(self):
        """Open the editor screen and hide the menu"""
        self.editor_window = editor.TreeEditor(self)
        self.editor_window.closed.connect(self.show)
        self.hide()
        self.editor_window.show()

    def open_options(self):
        """Button action: open the options screen."""
        print("Action: Opening options menu...")
        self.options_window = options.OptionsMenu(self)
        self.options_window.closed.connect(self.show)
        self.hide()
        self.options_window.show()

    def exit_program(self):
        """Button action: close the application gracefully."""
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
    # Create the application and show the main menu.
    app = QApplication(sys.argv)
    window = HomeMenu()
    window.show()
    sys.exit(app.exec())