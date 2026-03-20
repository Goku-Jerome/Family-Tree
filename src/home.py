import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import options
import editor

class HomeMenu(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Family Tree Creator")
        self.resize(800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()

        # --- Title ---
        self.title_label = QLabel("Family Tree Creator")
        # We don't set a fixed font size here anymore; resizeEvent handles it.
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addStretch(1)
        main_layout.addWidget(self.title_label)
        main_layout.addStretch(1)

        # --- Buttons ---
        button_actions = {
            "New Tree": self.create_new_tree,
            "Load Tree": self.load_existing_tree,
            "Options": self.open_options,
            "Exit": self.exit_program
        }

        # We need a list to store the actual button objects so we can 
        # update their fonts later when the window resizes.
        self.ui_buttons = []

        for name, function in button_actions.items():
            btn = QPushButton(name)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            
            # Store the button reference
            self.ui_buttons.append(btn)
            
            # The "Sandwich" Layout
            row_layout = QHBoxLayout()
            row_layout.addStretch(1) 
            row_layout.addWidget(btn, stretch=2) 
            row_layout.addStretch(1)
            
            main_layout.addLayout(row_layout)
            btn.clicked.connect(function)

        main_layout.addStretch(2)
        central_widget.setLayout(main_layout)

    # --- Responsive Text Logic ---
    def resizeEvent(self, event):
        """This function triggers automatically every time the window size changes."""
        super().resizeEvent(event) # Keep normal resize behaviors
        
        # Get the smaller dimension (width or height) to base our math on
        window_size = min(self.width(), self.height())
        
        # Calculate dynamic sizes (Math: roughly 6% of window size for title)
        # Using max() ensures the text never shrinks below a readable minimum (e.g., 16pt)
        dynamic_title_size = max(16, int(window_size * 0.1))
        dynamic_button_size = max(10, int(window_size * 0.05))

        # Apply to Title
        self.title_label.setFont(QFont("Arial", dynamic_title_size, QFont.Weight.Bold))
        
        # Apply to all Buttons
        button_font = QFont("Arial", dynamic_button_size)
        for btn in self.ui_buttons:
            btn.setFont(button_font)

    # --- Functions ---
    def create_new_tree(self):
        self.open_editor()

    def load_existing_tree(self):
        # Future: parse file and populate tree
        self.open_editor()

    def open_editor(self):
        self.editor_window = editor.TreeEditor(self)
        self.editor_window.closed.connect(self.show)
        self.hide()
        self.editor_window.show()

    def open_options(self):
        print("Action: Opening options menu...")
        self.options_window = options.OptionsMenu(self)
        self.options_window.closed.connect(self.show)
        self.hide()
        self.options_window.show()

    def exit_program(self):
        print("Action: Closing the application.")
        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HomeMenu()
    window.show()
    sys.exit(app.exec())