# editor.py
#
# Job:
# ----
# This module provides the central user interface (TreeEditor) and rendering engine
# for drawing the family tree interactively. It manages the scene canvas, handles
# node cards creation/placement, draws structural connector lines, captures mouse dragging/zooming,
# and supports file serialization/deserialization (saving/loading trees).
#
# How it works:
# -------------
# 1. Canvas Rendering (PyQt6 Graphics View framework): Uses QGraphicsScene to manage drawn items.
#    - Individual card nodes are represented by `NodeItem` (subclass of QGraphicsRectItem).
#    - Relationship lines are drawn dynamically as horizontal/vertical vector lines.
# 2. Delegated Placement & Visibility:
#    - Calls `visibility.calculate_visible_people(...)` to prune distant relatives from being drawn.
#    - Calls `layout.compute_layout(...)` to solve card coordinate placement (X, Y) without overlaps.
# 3. Mouse Mechanics: Uses custom mouse event filters on `PanGraphicsView` for panning (right click + drag)
#    and zooming (mouse wheel scroll).
# 4. JSON/XML File I/O: Saves and loads family trees by mapping the person registry into key/value dicts.

import sys
import json
import xml.etree.ElementTree as ET
import collections

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QMessageBox,
    QInputDialog,
    QFileDialog,
    QSizePolicy,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QDialog,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QDateEdit,
    QCheckBox,
    QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QTimer
from PyQt6.QtGui import QFont, QPen, QBrush, QPainter, QColor

from person import Person
from relation import find_relationship_bfs, get_relationship_title
import options
import layout
import visibility

# ─────────────────────────────────────────────────────────────────────────────
#  Layout Dimensions & Color Themes (Matching layout.py and Family Echo style)
# ─────────────────────────────────────────────────────────────────────────────
NODE_W          = 140   # Width of each person's card
NODE_H          =  56   # Height of each person's card
COUPLE_GAP      =  18   # Spacing between partner cards in a couple block
MAX_VISIBLE      = 200   # Max cards drawn on canvas before culling kicks in
LAYOUT_ITERS     =   8   # Number of layout relaxation iterations

# Color Palettes (RGB Hex values)
COL_MALE        = QColor("#d6e8f7")   # Soft pastel blue for male cards
COL_FEMALE      = QColor("#fce4ec")   # Soft pastel pink for female cards
COL_OTHER       = QColor("#f3e5f5")   # Lavender background for other/unspecified genders
COL_SELECTED_BG = QColor("#fff9c4")   # Yellow highlight for currently selected person
COL_BORDER_NORM = QColor("#546e7a")   # Muted grey-blue border for normal cards
COL_BORDER_SEL  = QColor("#e53935")   # Red border for selected card
COL_LINE_COUPLE = QColor("#1565c0")   # Dark blue lines connecting couples
COL_LINE_CHILD  = QColor("#2e7d32")   # Dark green lines connecting parents to children


class NodeItem(QGraphicsRectItem):
    """
    Job:
    ----
    A drawable rounded rectangle card representing one person on the scene.
    Displays names and dates of birth, changing colors when selected or based on gender.
    """
    def __init__(self, person: Person, callback):
        """
        Initializes the node shape, adds text sub-labels, and wires selection click triggers.
        """
        super().__init__(0, 0, NODE_W, NODE_H)
        self.person = person
        self.callback = callback
        
        # Enable selection flag for QGraphicsScene registry
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._selected = False
        self._apply_style()

        # Name label (handles display of first/last name with text wrap spacing)
        display = person.name
        self.label = QGraphicsTextItem(display, self)
        self.label.setDefaultTextColor(Qt.GlobalColor.black)
        self.label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.label.setTextWidth(NODE_W - 8)
        self.label.setPos(4, (NODE_H - self.label.boundingRect().height()) / 2)

        # Date of birth sub-label (positioned at the bottom edge of the card)
        if person.dob and person.dob != "Unknown":
            dob_label = QGraphicsTextItem(person.dob, self)
            dob_label.setDefaultTextColor(QColor("#555555"))
            dob_label.setFont(QFont("Arial", 7))
            dob_label.setPos(4, NODE_H - 16)

    def _bg_colour(self) -> QColor:
        """Determines card color according to active selection state and gender."""
        if self._selected:
            return COL_SELECTED_BG
        g = str(self.person.gender or "").lower()
        if g.startswith("m"):   
            return COL_MALE
        if g.startswith("f"):   
            return COL_FEMALE
        return COL_OTHER

    def _apply_style(self):
        """Redraws background fill brushes and borders."""
        self.setBrush(QBrush(self._bg_colour()))
        pen_col   = COL_BORDER_SEL if self._selected else COL_BORDER_NORM
        pen_width = 3             if self._selected else 1.5
        self.setPen(QPen(pen_col, pen_width))

    def update_style(self, selected: bool = False):
        """Exposed method to toggle selection highlighting and force border updates."""
        self._selected = selected
        self._apply_style()

    def mousePressEvent(self, event):
        """Overwritten Qt handler. Trigger callback to update selection index in editor."""
        super().mousePressEvent(event)
        if callable(self.callback):
            self.callback(self.person)


class PanGraphicsView(QGraphicsView):
    """
    Job:
    ----
    Wraps QGraphicsView to allow right-click dragging (panning) around the canvas
    and scroll-wheel zooming.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._panning = False
        self._pan_start = None

    def mousePressEvent(self, event):
        """Captures start location when right-click is pressed to start panning."""
        if event.button() == Qt.MouseButton.RightButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Scrolls canvas scrollbars relative to mouse movement offsets."""
        if self._panning and self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Restores arrow cursor when right-click is released."""
        if event.button() == Qt.MouseButton.RightButton and self._panning:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """Scales scene view up or down by 15% step increments on mouse scrolls."""
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class PersonDialog(QDialog):
    """
    Job:
    ----
    A pop-up modal input dialog. Captures first name, last name, gender, and date of birth.
    Pre-populates forms if an existing Person object is supplied (Edit mode).
    """
    def __init__(self, parent=None, title="New Person", person: Person = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Name inputs
        self.first_name_input = QLineEdit()
        self.last_name_input  = QLineEdit()

        # Date of birth inputs (Checkbox controls visibility/enabling of the date picker widget)
        self.dob_known_checkbox = QCheckBox("Date of Birth Known")
        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDisplayFormat("yyyy-MM-dd")

        # Gender selection controls
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Male", "Female", "Other"])
        self.gender_combo.currentIndexChanged.connect(self.on_gender_changed)

        # Field to specify custom gender descriptions if "Other" is chosen
        self.other_gender_input = QLineEdit()
        self.other_gender_input.setPlaceholderText("Please specify...")
        self.other_gender_input.setVisible(False)

        # Append fields to UI structure layout
        form_layout.addRow("First Name:",    self.first_name_input)
        form_layout.addRow("Last Name:",     self.last_name_input)
        form_layout.addRow("Gender:",        self.gender_combo)
        form_layout.addRow("",               self.other_gender_input)
        form_layout.addRow("Date of Birth:", self.dob_known_checkbox)
        form_layout.addRow("",               self.dob_input)

        # Accept / Reject buttons (Ok / Cancel)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form_layout)
        layout.addWidget(buttons)

        # Listeners to update element visibilities based on checks
        self.dob_known_checkbox.stateChanged.connect(self.on_dob_known_changed)

        # Pre-fill forms if an existing person reference is supplied
        if person:
            self.first_name_input.setText(person.first_name)
            self.last_name_input.setText(person.last_name)
            if person.dob != "Unknown":
                self.dob_known_checkbox.setChecked(True)
                date = QDate.fromString(person.dob, "yyyy-MM-dd")
                if date.isValid():
                    self.dob_input.setDate(date)
            else:
                self.dob_known_checkbox.setChecked(False)
            
            if person.gender:
                g = str(person.gender).lower()
                if g.startswith('m'):   
                    self.gender_combo.setCurrentIndex(0)
                elif g.startswith('f'): 
                    self.gender_combo.setCurrentIndex(1)
                else:
                    self.gender_combo.setCurrentIndex(2)
                    self.other_gender_input.setText(person.gender)
        else:
            self.dob_known_checkbox.setChecked(False)

        self.on_dob_known_changed()
        self.on_gender_changed()

    def on_dob_known_changed(self):
        """Enables date picker widget only when the checkbox is ticked."""
        self.dob_input.setEnabled(self.dob_known_checkbox.isChecked())

    def on_gender_changed(self):
        """Shows custom text box only when 'Other' option is selected in the gender dropdown."""
        self.other_gender_input.setVisible(self.gender_combo.currentText() == "Other")

    def get_data(self) -> dict:
        """
        Job:
        ----
        Collects form values from inputs and outputs a formatted dict.
        """
        dob = (self.dob_input.date().toString("yyyy-MM-dd")
               if self.dob_known_checkbox.isChecked() else "Unknown")
        gs = self.gender_combo.currentText()
        if gs == "Other" and self.other_gender_input.text().strip():
            gender = self.other_gender_input.text().strip()
        elif gs == "Male":   
            gender = "Male"
        elif gs == "Female": 
            gender = "Female"
        else:                
            gender = None
        return {
            "first_name": self.first_name_input.text().strip(),
            "last_name":  self.last_name_input.text().strip(),
            "dob":        dob,
            "gender":     gender,
        }


class TreeEditor(QMainWindow):
    """
    Main visual tree editor workspace window. Manages graph view, details panel,
    relationship modifications, search selectors, and serialization utilities.
    """
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Family Tree Editor")
        self.resize(1100, 700)

        # Core database state
        self.people = {}             # Map: person_id (str) -> Person object
        self.current_person = None   # Person object currently selected
        self.compare_person = None   # Person object chosen in details panel to compute relations path
        self.node_items = {}         # Map: person_id (str) -> NodeItem object in the active graphics scene

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout()
        central_widget.setLayout(self.main_layout)

        # Top Title banner
        self.title_label = QLabel("Family Tree Editor")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        self.main_layout.addWidget(self.title_label)

        # ── Setup Top Control Panel Row ──
        top_control = QHBoxLayout()
        self.create_root_button = QPushButton("Create Person")
        self.create_root_button.clicked.connect(self.create_root_person)
        self.create_root_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.save_button = QPushButton("Save Tree")
        self.save_button.clicked.connect(self.save_tree)
        self.save_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.load_button = QPushButton("Load Tree")
        self.load_button.clicked.connect(self.load_tree)
        self.load_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        top_control.addWidget(self.create_root_button)
        top_control.addWidget(self.save_button)
        top_control.addWidget(self.load_button)
        top_control.addWidget(QLabel("Current Person:"))
        self.person_selector = QComboBox()
        self.person_selector.currentIndexChanged.connect(self.on_person_selected)
        top_control.addWidget(self.person_selector)
        self.main_layout.addLayout(top_control)

        # ── Setup Graphics Canvas & Right Details Panel Splitter ──
        graph_layout = QHBoxLayout()
        self.scene = QGraphicsScene()
        self.view  = PanGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        graph_layout.addWidget(self.view, stretch=3)

        # Details Panel elements
        info_panel = QVBoxLayout()
        self.name_label      = QLabel("Name: -")
        self.relations_label = QLabel("Relations: -")
        self.edit_button     = QPushButton("Edit Person")
        self.edit_button.clicked.connect(self.edit_current_person)
        self.delete_button   = QPushButton("Delete Person")
        self.delete_button.clicked.connect(self.delete_current_person)
        info_panel.addWidget(self.name_label)
        info_panel.addWidget(self.relations_label)
        info_panel.addWidget(self.edit_button)
        info_panel.addWidget(self.delete_button)

        info_panel.addWidget(QLabel("─" * 40))
        
        # Relationship Path Calculator widgets
        cmp_lbl = QLabel("Relationship Comparison")
        cmp_lbl.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        info_panel.addWidget(cmp_lbl)
        info_panel.addWidget(QLabel("Compare with:"))
        
        self.compare_person_selector = QComboBox()
        self.compare_person_selector.currentIndexChanged.connect(self.on_compare_person_changed)
        info_panel.addWidget(self.compare_person_selector)
        
        self.blood_relation_label = QLabel("Blood Relation: -")
        self.full_relation_label  = QLabel("Full Relation: -")
        self.is_related_label     = QLabel("Related: -")
        info_panel.addWidget(self.blood_relation_label)
        info_panel.addWidget(self.full_relation_label)
        info_panel.addWidget(self.is_related_label)
        info_panel.addStretch(1)
        
        graph_layout.addLayout(info_panel, stretch=1)
        self.main_layout.addLayout(graph_layout)

        # ── Setup Bottom Actions Button Row ──
        self.buttons_layout = QHBoxLayout()
        self.parent_button  = QPushButton("Add Parent")
        self.parent_button.clicked.connect(lambda: self.manage_relationship("parent"))
        self.child_button   = QPushButton("Add Child")
        self.child_button.clicked.connect(lambda: self.manage_relationship("child"))
        self.partner_button = QPushButton("Add/Set Partner")
        self.partner_button.clicked.connect(lambda: self.manage_relationship("partner"))
        
        self.buttons_layout.addWidget(self.parent_button)
        self.buttons_layout.addWidget(self.child_button)
        self.buttons_layout.addWidget(self.partner_button)
        self.main_layout.addLayout(self.buttons_layout)

        # Initialize screen elements, stylesheets, and auto-save timers
        self.update_ui_state()
        self.apply_settings()
        self.setup_auto_save()

    # ── Window Event Overrides ──
    def resizeEvent(self, event):
        """Updates header text size dynamically when window is stretched."""
        super().resizeEvent(event)
        window_size    = min(self.width(), self.height())
        settings       = options.OptionsMenu.get_settings()
        base_font_size = settings.get('font_size', 12)
        self.title_label.setFont(QFont("Arial", max(base_font_size + 6, int(window_size * 0.03)), QFont.Weight.Bold))

    def apply_settings(self):
        """Fetches base settings and applies theme stylesheets."""
        options.OptionsMenu.apply_theme_to_window(self)
        settings       = options.OptionsMenu.get_settings()
        base_font_size = settings.get('font_size', 12)
        self.title_label.setFont(QFont("Arial", base_font_size + 10, QFont.Weight.Bold))

    def setup_auto_save(self):
        """Starts a background timer to save work every 30 seconds if auto-save is enabled."""
        settings = options.OptionsMenu.get_settings()
        if settings.get('auto_save', False):
            self.auto_save_timer = QTimer(self)
            self.auto_save_timer.timeout.connect(self.auto_save_tree)
            self.auto_save_timer.start(30000)
        else:
            if hasattr(self, 'auto_save_timer'):
                self.auto_save_timer.stop()

    def auto_save_tree(self):
        """Timer callback. Writes dictionary representation to 'family_tree.json' silently."""
        if self.people:
            try:
                self.serialize_json("family_tree.json")
                print("Auto-saved family tree")
            except Exception as e:
                print(f"Auto-save failed: {e}")

    def closeEvent(self, event):
        """Fires signal to tell parent menu to show itself again before closed."""
        self.closed.emit()
        super().closeEvent(event)

    # ── UI State Updating Helpers ──
    def update_ui_state(self):
        """
        Job:
        ----
        Forces refresh of active inputs, rebuilds lists, redraws vectors on the canvas,
        and displays details of the selected individual.
        """
        has_person = bool(self.people)
        self.person_selector.setEnabled(has_person)
        self.parent_button.setEnabled(self.current_person is not None)
        self.child_button.setEnabled(self.current_person is not None)
        self.partner_button.setEnabled(self.current_person is not None)
        self.edit_button.setEnabled(self.current_person is not None)
        
        self.refresh_person_selector()
        self.refresh_graph()
        
        if self.current_person:
            self.display_current_person()
        else:
            self.name_label.setText("Name: -")
            self.relations_label.setText("Relations: -")

    def refresh_person_selector(self):
        """Re-populates selection lists (and comparison lists) with the active registry."""
        selected_id = self.current_person.id if self.current_person else None
        
        # Block events temporarily to avoid feedback loops during dropdown rebuilds
        self.person_selector.blockSignals(True)
        self.person_selector.clear()
        self.person_selector.addItem("Select person", None)
        for p in self.people.values():
            self.person_selector.addItem(f"{p.name} ({p.id[:8]})", p.id)
        if selected_id:
            for i in range(self.person_selector.count()):
                if self.person_selector.itemData(i) == selected_id:
                    self.person_selector.setCurrentIndex(i)
                    break
        self.person_selector.blockSignals(False)

        cmp_id = self.compare_person.id if self.compare_person else None
        self.compare_person_selector.blockSignals(True)
        self.compare_person_selector.clear()
        self.compare_person_selector.addItem("Select person to compare", None)
        for p in self.people.values():
            self.compare_person_selector.addItem(f"{p.name} ({p.id[:8]})", p.id)
        if cmp_id:
            for i in range(self.compare_person_selector.count()):
                if self.compare_person_selector.itemData(i) == cmp_id:
                    self.compare_person_selector.setCurrentIndex(i)
                    break
        self.compare_person_selector.blockSignals(False)
        self.on_compare_person_changed()

    def on_person_selected(self):
        """Dropdown handler. Updates active focus selection when selection changes."""
        sid = self.person_selector.currentData()
        if sid and sid in self.people:
            self.set_current_person(self.people[sid])

    def on_compare_person_changed(self):
        """Dropdown handler. Updates target comparison selection and prompts recalculations."""
        sid = self.compare_person_selector.currentData()
        self.compare_person = self.people.get(sid) if sid else None
        self.update_relationship_display()

    def update_relationship_display(self):
        """
        Job:
        ----
        Computes the relationship path between current selection and comparison target.
        Displays title and breadcrumbs.
        """
        if not self.current_person or not self.compare_person:
            self.blood_relation_label.setText("Relation: -")
            self.full_relation_label.setText("Path: -")
            self.is_related_label.setText("Related: -")
            return
            
        if self.current_person is self.compare_person:
            self.blood_relation_label.setText("Relation: Self")
            self.full_relation_label.setText("Path: Same person")
            self.is_related_label.setText("Related: Yes (self)")
            return
            
        # Call BFS calculations from relation module
        result = find_relationship_bfs(self.current_person, self.compare_person)
        if result:
            relationship_title = get_relationship_title(result)
            path, is_in_law    = result
            path_str           = " → ".join([p.name for p in path])
            relation_text = relationship_title if relationship_title and relationship_title != "No relationship found" else "Not related"
            
            self.blood_relation_label.setText(f"Relation: {relation_text}")
            self.full_relation_label.setText(f"Path: {path_str}")
            self.is_related_label.setText("Related: Yes")
        else:
            self.blood_relation_label.setText("Relation: Not related")
            self.full_relation_label.setText("Path: No path found")
            self.is_related_label.setText("Related: No")

    def set_current_person(self, person: Person):
        """Sets selected focus person, highlights their card on canvas, and updates text panel."""
        self.current_person = person
        for node in self.node_items.values():
            # Update selection style on the graphic card node
            node.update_style(selected=(node.person is person))
        self.update_ui_state()

    def display_current_person(self):
        """Updates text label panels with current selection biography details."""
        if not self.current_person:
            return
        self.name_label.setText(
            f"Name: {self.current_person.name} | DOB: {self.current_person.dob} | ID: {self.current_person.id[:8]}")
        parents  = ", ".join(p.name for p in self.current_person.parents) or "None"
        children = ", ".join(c.name for c in self.current_person.children) or "None"
        partner  = self.current_person.partner.name if self.current_person.partner else "None"
        self.relations_label.setText(f"Parents: {parents}\nChildren: {children}\nPartner: {partner}")

    # ── CRUD database actions ──
    def delete_current_person(self):
        """Sever relationships, delete from memory database, and clear selection."""
        if not self.current_person:
            return
        confirm = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete {self.current_person.name}?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.current_person.delete()
            if self.current_person.id in self.people:
                del self.people[self.current_person.id]
            self.current_person = None
            self.update_ui_state()

    def edit_current_person(self):
        """Launches Edit modal, updating details of selection upon confirmation."""
        if not self.current_person:
            return
        dialog = PersonDialog(self, "Edit Person", self.current_person)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["first_name"]:
                QMessageBox.warning(self, "Invalid Input", "First name cannot be empty.")
                return
            if not data["last_name"]:
                QMessageBox.warning(self, "Invalid Input", "Last name cannot be empty.")
                return
            
            # Write form updates to object attributes
            self.current_person.first_name = data["first_name"]
            self.current_person.last_name  = data["last_name"]
            self.current_person.name       = f"{data['first_name']} {data['last_name']}".strip()
            self.current_person.dob        = data["dob"]
            self.current_person.gender     = data["gender"]
            self.update_ui_state()

    def create_root_person(self):
        """Launches New Person modal, registers them as the main root of a tree."""
        new_person = self.create_person_dialog("Root person")
        if new_person:
            self.people[new_person.id] = new_person
            self.set_current_person(new_person)
            self.update_ui_state()

    def create_person_dialog(self, title: str) -> Optional[Person]:
        """Utility launching Person Dialog. Returns a new Person object or None if cancelled."""
        dialog = PersonDialog(self, title)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        data = dialog.get_data()
        return Person(
            first_name=data["first_name"] or None,
            last_name=data["last_name"]   or None,
            dob=data["dob"]               or None,
            gender=data["gender"],
        )

    def choose_existing_person(self, exclude: Person = None) -> Optional[Person]:
        """Presents dialog picker containing list of database records. Returns choice or None."""
        candidates = [p for p in self.people.values() if p is not exclude]
        if not candidates:
            QMessageBox.information(self, "No Existing Person", "No existing person available.")
            return None
        opts = [f"{p.name} ({p.id[:8]})" for p in candidates]
        item, ok = QInputDialog.getItem(self, "Choose Person", "Select existing person:", opts, editable=False)
        if ok and item:
            for p in candidates:
                if item.startswith(p.name):
                    return p
        return None

    # ── Relationship Visibility (Delegated to visibility.py) ──
    def get_visible_people(self) -> set[Person]:
        """
        Job:
        ----
        Invokes the visibility module to filter the display set around the selection.
        """
        return visibility.calculate_visible_people(self.current_person, self.people, max_visible=MAX_VISIBLE)

    # ── Database Serialization / File I/O ──
    def build_person_data(self, person: Person) -> dict:
        """Translates a Person instance attributes and relationships into serializable dictionary fields."""
        return {
            "id":         person.id,
            "first_name": person.first_name,
            "last_name":  person.last_name,
            "dob":        person.dob,
            "gender":     person.gender,
            "parents":    [p.id for p in person.parents],
            "children":   [c.id for c in person.children],
            "partner":    person.partner.id if person.partner else None,
        }

    def to_dict(self) -> dict:
        """Wraps all database records into single object dictionary structure."""
        return {"people": [self.build_person_data(p) for p in self.people.values()]}

    def serialize_json(self, path: str):
        """Dumps dictionary schema into formatted JSON file on disk."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def serialize_xml(self, path: str):
        """Constructs XML element tree structure and dumps to file on disk."""
        root = ET.Element("family_tree")
        for person in self.people.values():
            p_elem = ET.SubElement(root, "person", attrib={"id": person.id})
            ET.SubElement(p_elem, "first_name").text = person.first_name
            ET.SubElement(p_elem, "last_name").text  = person.last_name
            ET.SubElement(p_elem, "dob").text        = person.dob
            parents_elem = ET.SubElement(p_elem, "parents")
            for pid in [p.id for p in person.parents]:
                ET.SubElement(parents_elem, "parent").text = pid
            children_elem = ET.SubElement(p_elem, "children")
            for cid in [c.id for c in person.children]:
                ET.SubElement(children_elem, "child").text = cid
            ET.SubElement(p_elem, "partner").text = person.partner.id if person.partner else ""
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

    def load_from_dict(self, data: dict):
        """
        Job:
        ----
        Rebuilds database instances and connects pointer references from standard dictionary structures.
        """
        self.people.clear()
        self.current_person = None
        
        # Pass 1: Instantiate blank Person objects (resolves lookup ID directories)
        for p_data in data.get("people", []):
            p = Person(
                first_name=p_data.get("first_name"),
                last_name=p_data.get("last_name"),
                dob=p_data.get("dob"),
                person_id=p_data.get("id"),
                gender=p_data.get("gender"),
            )
            self.people[p.id] = p
            
        # Pass 2: Connect parent, child, and spouse reference pointers using maps
        for p_data in data.get("people", []):
            p = self.people.get(p_data["id"])
            if not p: 
                continue
            for pid in p_data.get("parents", []):
                par = self.people.get(pid)
                if par: 
                    p.add_parent(par)
            for cid in p_data.get("children", []):
                ch = self.people.get(cid)
                if ch: 
                    p.add_child(ch)
            partner_id = p_data.get("partner")
            if partner_id:
                partner = self.people.get(partner_id)
                if partner: 
                    p.set_partner(partner)
                    
        # Select first available person as default selection
        if self.people:
            self.set_current_person(next(iter(self.people.values())))
        self.update_ui_state()

    def deserialize_json(self, path: str):
        """Loads and parses JSON files into dictionary structure."""
        with open(path, "r", encoding="utf-8") as f:
            self.load_from_dict(json.load(f))

    def deserialize_xml(self, path: str):
        """Parses XML files, extracting fields to populate dictionary structure."""
        tree = ET.parse(path)
        root = tree.getroot()
        data = {"people": []}
        for p_elem in root.findall("person"):
            pid        = p_elem.get("id")
            first_name = p_elem.findtext("first_name", "Unnamed")
            last_name  = p_elem.findtext("last_name", "Unnamed")
            dob        = p_elem.findtext("dob", "Unknown")
            parents    = [c.text for c in p_elem.find("parents") or [] if c.text]
            children   = [c.text for c in p_elem.find("children") or [] if c.text]
            partner    = p_elem.findtext("partner", "") or None
            data["people"].append({
                "id": pid, "first_name": first_name, "last_name": last_name,
                "dob": dob, "parents": parents, "children": children, "partner": partner,
            })
        self.load_from_dict(data)

    def save_tree(self):
        """Displays system Save Dialog file window. Serializes database based on extension."""
        settings = options.OptionsMenu.get_settings()
        default_format = settings.get('export_format', 'JSON')
        if default_format == 'XML':
            default_name = "family_tree.xml"
            file_filter  = "XML Files (*.xml);;JSON Files (*.json)"
        else:
            default_name = "family_tree.json"
            file_filter  = "JSON Files (*.json);;XML Files (*.xml)"
            
        path, selected = QFileDialog.getSaveFileName(self, "Save Family Tree", default_name, file_filter)
        if not path: 
            return
        try:
            if path.lower().endswith(".xml") or selected.startswith("XML"):
                self.serialize_xml(path)
            else:
                self.serialize_json(path)
            QMessageBox.information(self, "Save Successful", f"Saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save:\n{e}")

    def load_tree(self):
        """Displays system Open Dialog file window. Deserializes data based on extension."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Family Tree", "", "JSON Files (*.json);;XML Files (*.xml)")
        if not path: 
            return
        try:
            if path.lower().endswith(".xml"):
                self.deserialize_xml(path)
            else:
                self.deserialize_json(path)
            QMessageBox.information(self, "Load Successful", f"Loaded from {path}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load:\n{e}")

    def manage_relationship(self, relationship: str):
        """
        Job:
        ----
        Core relationship link builder. Guides adding parent, child, or partners
        by spawning dialogs and updating target pointer tables.
        """
        if not self.current_person:
            return
        choice, ok = QInputDialog.getItem(
            self, "Relationship Action", "Choose action:",
            ["Create New Person", "Add Existing Person"], editable=False)
        if not ok: 
            return

        target = None
        if choice == "Create New Person":
            target = self.create_person_dialog(f"Create {relationship.title()}")
            if target:
                self.people[target.id] = target
        elif choice == "Add Existing Person":
            target = self.choose_existing_person(exclude=self.current_person)
        if not target: 
            return

        if relationship == "parent":
            # Add child link directions
            self.current_person.add_parent(target)
            target.add_child(self.current_person)
            
            # If person now has exactly 2 parents, link the parents as partners automatically
            if len(self.current_person.parents) == 2:
                p1, p2 = list(self.current_person.parents)[:2]
                p1.set_partner(p2)
                p2.set_partner(p1)
                
        elif relationship == "child":
            self.current_person.add_child(target)
            target.add_parent(self.current_person)
            
            # If parent has partner, add the child to partner's children automatically
            if self.current_person.partner:
                self.current_person.partner.add_child(target)
                target.add_parent(self.current_person.partner)
                
        elif relationship == "partner":
            self.current_person.set_partner(target)
            target.set_partner(self.current_person)

        self.set_current_person(self.current_person)

    # ── Layout Rendering & Drawing (Calls layout.py computation coordinates) ──
    def refresh_graph(self):
        """
        Job:
        ----
        Primary rendering sweep. Clears old layout, fetches coordinates from the layout engine,
        spawns NodeItem cards at calculated positions, and draws orthogonal lines connecting them.
        """
        self.scene.clear()
        self.node_items = {}

        if not self.people:
            self.scene.addText("Create or load a person to start your tree.")
            return

        visible = self.get_visible_people()
        if not visible:
            return

        # Choose focus seed person
        focus = self.current_person if self.current_person in visible else next(iter(visible))

        # ── 1. Calculate positions using layout engine module ──
        units, p2u = layout.compute_layout(visible, focus_person=focus, layout_iters=LAYOUT_ITERS)

        # ── 2. Instantiate and position node items ──
        for unit in units:
            if len(unit.members) == 1:
                p = unit.members[0]
                node = NodeItem(p, self.set_current_person)
                # Position single-card unit centered horizontally
                node.setPos(unit.x - NODE_W / 2, unit.y)
                self.scene.addItem(node)
                self.node_items[p.id] = node
            else:
                p1, p2 = unit.members[0], unit.members[1]
                n1 = NodeItem(p1, self.set_current_person)
                n2 = NodeItem(p2, self.set_current_person)
                # Position couple cards side-by-side with a gap between them
                x1 = unit.x - COUPLE_GAP / 2 - NODE_W
                x2 = unit.x + COUPLE_GAP / 2
                n1.setPos(x1, unit.y)
                n2.setPos(x2, unit.y)
                self.scene.addItem(n1)
                self.scene.addItem(n2)
                self.node_items[p1.id] = n1
                self.node_items[p2.id] = n2

        # ── 3. Draw connecting lines ──
        self._draw_lines(units, visible, p2u)

        # ── 4. Set selection highlight ──
        if self.current_person and self.current_person.id in self.node_items:
            self.node_items[self.current_person.id].update_style(True)

        # Auto-resize scene viewport margins
        bounds = self.scene.itemsBoundingRect().adjusted(-80, -80, 80, 80)
        self.scene.setSceneRect(bounds)
        
        # Center camera view on selected person card
        if self.current_person and self.current_person.id in self.node_items:
            self.view.centerOn(self.node_items[self.current_person.id])

    def _line(self, x1: float, y1: float, x2: float, y2: float, pen: QPen):
        """Draws a vector line segment behind card nodes (Z-Value = -1)."""
        item = self.scene.addLine(x1, y1, x2, y2, pen)
        item.setZValue(-1)
        return item

    def _draw_lines(self, units: list[layout.FamilyUnit], visible: set[Person], p2u: dict):
        """
        Job:
        ----
        Draws connection paths:
        1. Spouse lines (dark blue) between partner cards.
        2. Child lines (dark green) dropping from couples mid-bridge down to child top-edges.
        """
        couple_pen  = QPen(COL_LINE_COUPLE, 1.8, Qt.PenStyle.SolidLine)
        child_pen   = QPen(COL_LINE_CHILD,  1.8, Qt.PenStyle.SolidLine)

        drawn_couple = set()
        couple_drop_x = {} # Maps couple set -> midpoint X where child lines drop from

        # ── Draw Spouse Lines ──
        for unit in units:
            if len(unit.members) != 2:
                continue
            p1, p2 = unit.members
            key = frozenset([p1.id, p2.id])
            if key in drawn_couple:
                continue
            drawn_couple.add(key)

            n1 = self.node_items.get(p1.id)
            n2 = self.node_items.get(p2.id)
            if not (n1 and n2):
                continue

            r1 = n1.sceneBoundingRect()
            r2 = n2.sceneBoundingRect()
            mid_y = (r1.center().y() + r2.center().y()) / 2

            # Horizontal connector bridge from right edge of partner 1 to left edge of partner 2
            self._line(r1.right(), mid_y, r2.left(), mid_y, couple_pen)

            # Store mid-point coordinates for child drop lines
            drop_x = (r1.right() + r2.left()) / 2
            couple_drop_x[key] = drop_x

        # ── Draw Child Lines ──
        for unit in units:
            children_vis = []
            for m in unit.members:
                for ch in m.children:
                    if ch.id in self.node_items:
                        children_vis.append(ch)

            # De-duplicate list preserving relationship indices
            seen = set()
            ch_dedup = []
            for ch in children_vis:
                if ch.id not in seen:
                    seen.add(ch.id)
                    ch_dedup.append(ch)
            children_vis = ch_dedup

            if not children_vis:
                continue

            # Determine where the line leaves the parent unit block
            if len(unit.members) == 2:
                p1, p2 = unit.members
                key = frozenset([p1.id, p2.id])
                origin_x = couple_drop_x.get(key, unit.x)
                r1 = self.node_items[p1.id].sceneBoundingRect() if p1.id in self.node_items else None
                r2 = self.node_items[p2.id].sceneBoundingRect() if p2.id in self.node_items else None
                if r1 and r2:
                    origin_y = (r1.bottom() + r2.bottom()) / 2
                else:
                    origin_y = unit.y + NODE_H
            else:
                p = unit.members[0]
                if p.id not in self.node_items:
                    continue
                r = self.node_items[p.id].sceneBoundingRect()
                origin_x = r.center().x()
                origin_y = r.bottom()

            # Orthogonal connector line drawing style:
            # - For single children: vertical line down -> horizontal jog -> vertical down to card top.
            # - For multiple children: vertical down -> horizontal crossbar -> vertical drop down to each child.
            if len(children_vis) == 1:
                ch = children_vis[0]
                ch_r = self.node_items[ch.id].sceneBoundingRect()
                ch_x = ch_r.center().x()
                ch_y = ch_r.top()

                mid_y = (origin_y + ch_y) / 2
                self._line(origin_x, origin_y, origin_x, mid_y, child_pen)
                self._line(origin_x, mid_y, ch_x, mid_y, child_pen)
                self._line(ch_x, mid_y, ch_x, ch_y, child_pen)
            else:
                child_xs = []
                child_tops = []
                for ch in children_vis:
                    ch_r = self.node_items[ch.id].sceneBoundingRect()
                    child_xs.append(ch_r.center().x())
                    child_tops.append(ch_r.top())

                # Place crossbar at the middle of the vertical spacing gap
                nearest_child_top = min(child_tops)
                crossbar_y = origin_y + (nearest_child_top - origin_y) * 0.5

                # Draw drop line from parent to crossbar
                self._line(origin_x, origin_y, origin_x, crossbar_y, child_pen)

                # Draw crossbar horizontal line spanning all children
                bar_left  = min(child_xs)
                bar_right = max(child_xs)
                self._line(bar_left, crossbar_y, bar_right, crossbar_y, child_pen)

                # Draw downward vertical drops from crossbar down to each child's top edge
                for ch, cx, ct in zip(children_vis, child_xs, child_tops):
                    self._line(cx, crossbar_y, cx, ct, child_pen)

    # ── Legacy helpers kept for completeness ──
    def find_root_person(self, visible_people: set[Person]) -> Person:
        """Finds root ancestor person (who has no visible parents)."""
        candidates = [p for p in visible_people if not any(par in visible_people for par in p.parents)]
        return candidates[0] if candidates else next(iter(visible_people))

    def compute_levels(self, root: Person, visible_people: set[Person]) -> dict:
        """Performs traversal levels mappings, returning nodes grouped by generational level keys."""
        levels  = {}
        visited = set()
        queue   = [(root, 0)]
        while queue:
            person, level = queue.pop(0)
            if person.id in visited: 
                continue
            visited.add(person.id)
            levels.setdefault(level, []).append(person)
            for child in person.children:
                if child in visible_people and child.id not in visited:
                    queue.append((child, level + 1))
            if person.partner and person.partner in visible_people and person.partner.id not in visited:
                queue.append((person.partner, level))
            for parent in person.parents:
                if parent in visible_people and parent.id not in visited:
                    queue.append((parent, level - 1))
        for lvl in levels:
            levels[lvl] = list(dict.fromkeys(levels[lvl]))
        return levels


if __name__ == "__main__":
    app    = QApplication(sys.argv)
    window = TreeEditor()
    window.show()
    sys.exit(app.exec())