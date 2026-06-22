# options.py
#
# Job:
# ----
# This module defines the OptionsMenu window where users configure application
# settings (e.g. theme, font sizes, auto-save intervals, export format).
# It also handles loading and saving these preferences to a physical 'settings.json' file.
#
# How it works:
# -------------
# 1. Reading/Writing settings: When requested, it reads from or writes dictionary structures
#    to 'settings.json' in the parent directory. It provides safe defaults if the file is missing or corrupted.
# 2. Applying stylesheets: It provides a static method `apply_theme_to_window` that takes any
#    QMainWindow and applies standard CSS styling to implement Light/Dark mode.
# 3. Dynamic layout controls: Employs standard PyQt6 layouts and input widgets (QComboBox, QSpinBox, QCheckBox).
#    It also reacts to window resize events to adjust font sizes proportionally.

import sys
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QGroupBox, QCheckBox, QComboBox, QSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

class OptionsMenu(QMainWindow):
    """
    Settings configuration window. Allows customization of themes, sizes, and file export options.
    """
    closed = pyqtSignal() # Custom event signal fired when this window is closed

    def __init__(self, parent=None):
        """
        Job:
        ----
        Initializes the options window GUI, sets up container groups, and loads settings from file.
        """
        super().__init__(parent)

        self.setWindowTitle("Family Tree Creator - Options")
        self.resize(800, 600)

        # Base central container and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout()
        central_widget.setLayout(self.main_layout)

        # Title Label at top
        self.title_label = QLabel("Options")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addStretch(1)
        self.main_layout.addWidget(self.title_label)

        # Create settings fields grouped into sections
        self.section_containers = []
        self._build_sections()

        self.main_layout.addStretch(1)

        # Bottom buttons: Save, Cancel, Reset
        self.control_panel = self._make_button_row(
            {
                "Save": self.save_options,
                "Cancel": self.close,
                "Reset": self.reset_options,
            }
        )
        self.main_layout.addLayout(self.control_panel)

        self.setMinimumSize(640, 480)

        # Load preferences from disk
        self.load_options()

        # Apply current styling (Light / Dark mode colors)
        OptionsMenu.apply_theme_to_window(self)

    def get_settings_path(self) -> str:
        """
        Job:
        ----
        Returns the absolute filepath to 'settings.json'. It is situated in the directory
        directly above this script (the project root folder).
        """
        return os.path.join(os.path.dirname(__file__), '..', 'settings.json')

    def load_options(self):
        """
        Job:
        ----
        Loads saved preferences from disk and sets the values of GUI inputs (comboboxes/spinboxes/checkboxes).
        Fallback to defaults if file does not exist or has bad JSON syntax.
        """
        settings_path = self.get_settings_path()
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                # Populate widgets with loaded values
                self.theme_combo.setCurrentText(settings.get('theme', 'Light'))
                self.font_size_spin.setValue(settings.get('font_size', 12))
                self.auto_save_checkbox.setChecked(settings.get('auto_save', False))
                self.confirm_exit_checkbox.setChecked(settings.get('confirm_exit', True))
                self.default_format_combo.setCurrentText(settings.get('export_format', 'JSON'))
            except (json.JSONDecodeError, KeyError):
                # Corruption fallback
                self.reset_options()
        else:
            # File missing fallback
            self.reset_options()

    @staticmethod
    def get_settings() -> dict:
        """
        Job:
        ----
        A static helper method allowing any class (like HomeMenu or TreeEditor) to quickly fetch
        the settings dictionary from disk without having to instantiate the OptionsMenu.

        Returns:
        --------
        dict: Settings dictionary (e.g. {'theme': 'Light', 'font_size': 12, ...})
        """
        settings_path = os.path.join(os.path.dirname(__file__), '..', 'settings.json')
        defaults = {
            "theme": "Light",
            "font_size": 12,
            "auto_save": False,
            "confirm_exit": True,
            "export_format": "JSON",
        }
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                # Merge defaults to protect against missing keys in user config files
                return {**defaults, **settings}
            except (json.JSONDecodeError, KeyError):
                return defaults
        return defaults

    @staticmethod
    def apply_theme_to_window(window: QMainWindow):
        """
        Job:
        ----
        Applies style-sheet declarations (Qt CSS) to a window based on the active theme.

        How it does it:
        --------------
        - Reads the current theme value from settings.
        - If "Dark", applies custom dark-grey colors (#2b2b2b) and rounded borders to buttons/inputs.
        - If "Light", sets stylesheet to an empty string, reverting to native system colors.
        """
        settings = OptionsMenu.get_settings()
        theme = settings.get('theme', 'Light')
        
        if theme == 'Dark':
            dark_stylesheet = """
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QComboBox, QSpinBox {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 2px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555555;
                border-radius: 5px;
                margin-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            """
            window.setStyleSheet(dark_stylesheet)
        elif theme == 'Light':
            window.setStyleSheet("")

    def _build_sections(self):
        """
        Job:
        ----
        Assembles three settings groups (Display, Behavior, Export) and adds them to layout.
        """
        self.main_layout.addLayout(self._create_layout_section("Display", self._display_section_widgets()))
        self.main_layout.addLayout(self._create_layout_section("Behavior", self._behavior_section_widgets()))
        self.main_layout.addLayout(self._create_layout_section("Export", self._export_section_widgets()))

    def _create_layout_section(self, title: str, widgets: list[QWidget]) -> QHBoxLayout:
        """
        Job:
        ----
        Wraps widgets in a labeled QGroupBox to keep options visually distinct.
        """
        group = QGroupBox(title)
        layout = QVBoxLayout()
        for w in widgets:
            layout.addWidget(w)
        group.setLayout(layout)
        self.section_containers.append(group)

        # Draw box centered with stretching elements on the left and right
        row_layout = QHBoxLayout()
        row_layout.addStretch(1)
        row_layout.addWidget(group, stretch=8)
        row_layout.addStretch(1)
        return row_layout

    def _display_section_widgets(self) -> list[QWidget]:
        """Creates theme picker combobox and base font size spinner."""
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark", "System"])

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 40)
        self.font_size_spin.setValue(12)

        return [QLabel("Theme:"), self.theme_combo, QLabel("Base font size:"), self.font_size_spin]

    def _behavior_section_widgets(self) -> list[QWidget]:
        """Creates checkboxes for auto-save and exit confirmations."""
        self.auto_save_checkbox = QCheckBox("Enable Auto-Save")
        self.confirm_exit_checkbox = QCheckBox("Confirm before exit")
        return [self.auto_save_checkbox, self.confirm_exit_checkbox]

    def _export_section_widgets(self) -> list[QWidget]:
        """Creates file extension combobox for saving family trees."""
        self.default_format_combo = QComboBox()
        self.default_format_combo.addItems(["JSON", "XML", "PNG"])
        return [QLabel("Default export format:"), self.default_format_combo]

    def _make_button_row(self, buttons: dict) -> QHBoxLayout:
        """Builds bottom button row (Save, Cancel, Reset)."""
        row_layout = QHBoxLayout()
        for name, callback in buttons.items():
            btn = QPushButton(name)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(callback)
            row_layout.addWidget(btn)
        return row_layout

    def resizeEvent(self, event):
        """
        Job:
        ----
        Adjusts font sizes dynamically when the window is resized.
        """
        super().resizeEvent(event)
        settings = OptionsMenu.get_settings()
        base_font_size = settings.get('font_size', 12)
        
        window_size = min(self.width(), self.height())
        title_font_size = max(base_font_size + 4, int(window_size * 0.06))
        section_font_size = max(base_font_size - 2, int(window_size * 0.03))

        self.title_label.setFont(QFont("Arial", title_font_size, QFont.Weight.Bold))
        for group in self.section_containers:
            group.setFont(QFont("Arial", section_font_size, QFont.Weight.DemiBold))

    def closeEvent(self, event):
        """
        Job:
        ----
        Fires the 'closed' signal to notify the parent window (MainMenu) to show itself again
        before closing down options.
        """
        self.closed.emit()
        super().closeEvent(event)

    def save_options(self):
        """
        Job:
        ----
        Saves user choices to 'settings.json' and closes the options screen.
        """
        values = {
            "theme": self.theme_combo.currentText(),
            "font_size": self.font_size_spin.value(),
            "auto_save": self.auto_save_checkbox.isChecked(),
            "confirm_exit": self.confirm_exit_checkbox.isChecked(),
            "export_format": self.default_format_combo.currentText(),
        }
        settings_path = self.get_settings_path()
        try:
            with open(settings_path, 'w') as f:
                json.dump(values, f, indent=4)
            print("Options saved:", values)
        except Exception as e:
            print(f"Error saving options: {e}")
        self.close()

    def reset_options(self):
        """
        Job:
        ----
        Resets all input inputs in options dialog to default settings values.
        Does not automatically write to disk until user clicks 'Save'.
        """
        self.theme_combo.setCurrentText('Light')
        self.font_size_spin.setValue(12)
        self.auto_save_checkbox.setChecked(False)
        self.confirm_exit_checkbox.setChecked(True)
        self.default_format_combo.setCurrentText('JSON')
        print("Options reset to defaults in UI")


if __name__ == "__main__":
    # Allows options window to be run standalone for developer layout testing
    app = QApplication(sys.argv)
    window = OptionsMenu()
    window.show()
    sys.exit(app.exec())
