# options.py
# This module is the settings window for Family Tree Creator.
# It contains easy controls for display and behavior preferences.

import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QGroupBox, QCheckBox, QComboBox, QSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

class OptionsMenu(QMainWindow):
    """Window where the user can choose theme, font size, and export settings."""
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Family Tree Creator - Options")
        self.resize(800, 600)

        # Base container and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.main_layout = QVBoxLayout()
        central_widget.setLayout(self.main_layout)

        # Page title label
        self.title_label = QLabel("Options")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.main_layout.addStretch(1)
        self.main_layout.addWidget(self.title_label)

        # Build each options section
        self.section_containers = []
        self._build_sections()

        self.main_layout.addStretch(1)

        # Buttons at the bottom: Save, Cancel, Reset
        self.control_panel = self._make_button_row(
            {
                "Save": self.save_options,
                "Cancel": self.close,
                "Reset": self.reset_options,
            }
        )
        self.main_layout.addLayout(self.control_panel)

        self.setMinimumSize(640, 480)

    def _build_sections(self):
        """Make the three sections, each with labeled options."""
        self.main_layout.addLayout(self._create_layout_section("Display", self._display_section_widgets()))
        self.main_layout.addLayout(self._create_layout_section("Behavior", self._behavior_section_widgets()))
        self.main_layout.addLayout(self._create_layout_section("Export", self._export_section_widgets()))

    def _create_layout_section(self, title, widgets):
        """Wrap a group of controls with a titled box and center it."""
        group = QGroupBox(title)
        layout = QVBoxLayout()
        for w in widgets:
            layout.addWidget(w)
        group.setLayout(layout)
        self.section_containers.append(group)

        row_layout = QHBoxLayout()
        row_layout.addStretch(1)
        row_layout.addWidget(group, stretch=8)
        row_layout.addStretch(1)
        return row_layout

    def _display_section_widgets(self):
        """Create controls for display options."""
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark", "System"])

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 40)
        self.font_size_spin.setValue(12)

        return [QLabel("Theme:"), self.theme_combo, QLabel("Base font size:"), self.font_size_spin]

    def _behavior_section_widgets(self):
        """Create checkboxes for behavior options."""
        self.auto_save_checkbox = QCheckBox("Enable Auto-Save")
        self.confirm_exit_checkbox = QCheckBox("Confirm before exit")
        return [self.auto_save_checkbox, self.confirm_exit_checkbox]

    def _export_section_widgets(self):
        """Create export format selector."""
        self.default_format_combo = QComboBox()
        self.default_format_combo.addItems(["JSON", "XML", "PNG"])

        return [QLabel("Default export format:"), self.default_format_combo]

    def _make_button_row(self, buttons):
        """Build the horizontal row of action buttons at bottom."""
        row_layout = QHBoxLayout()
        for name, callback in buttons.items():
            btn = QPushButton(name)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(callback)
            row_layout.addWidget(btn)
        return row_layout

    def resizeEvent(self, event):
        """Adjusts the text size to keep text readable when window resizes."""
        super().resizeEvent(event)
        window_size = min(self.width(), self.height())
        title_font_size = max(16, int(window_size * 0.06))
        section_font_size = max(10, int(window_size * 0.03))

        self.title_label.setFont(QFont("Arial", title_font_size, QFont.Weight.Bold))
        for group in self.section_containers:
            group.setFont(QFont("Arial", section_font_size, QFont.Weight.DemiBold))

    def closeEvent(self, event):
        """Let the parent know this window was closed."""
        self.closed.emit()
        super().closeEvent(event)

    def save_options(self):
        """Collect values from controls and close window."""
        values = {
            "theme": self.theme_combo.currentText(),
            "font_size": self.font_size_spin.value(),
            "auto_save": self.auto_save_checkbox.isChecked(),
            "confirm_exit": self.confirm_exit_checkbox.isChecked(),
            "export_format": self.default_format_combo.currentText(),
        }
        print("Options saved:", values)
        self.close()

    def reset_options(self):
        """Restore default options state."""
        self.theme_combo.setCurrentIndex(0)
        self.font_size_spin.setValue(12)
        self.auto_save_checkbox.setChecked(False)
        self.confirm_exit_checkbox.setChecked(True)
        self.default_format_combo.setCurrentIndex(0)
        print("Options reset to defaults")


if __name__ == "__main__":
    # This allows running options.py directly for quick testing.
    app = QApplication(sys.argv)
    window = OptionsMenu()
    window.show()
    sys.exit(app.exec())
