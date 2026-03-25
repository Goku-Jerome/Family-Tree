# editor.py
# This module is the main family tree editor window and drawing engine.
# It creates a visual graph of people with interactive selection and actions.

import sys
import json
import xml.etree.ElementTree as ET

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
    QVBoxLayout,
    QDateEdit,
    QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QPen, QBrush, QPainter
from person import Person
from relation import find_relationship, find_blood_relationship, detect_blood_relation


class NodeItem(QGraphicsRectItem):
    """A single rectangle representing one person in the visualization."""
    WIDTH = 130
    HEIGHT = 60

    def __init__(self, person, callback):
        super().__init__(0, 0, NodeItem.WIDTH, NodeItem.HEIGHT)
        self.person = person
        self.callback = callback

        self.setBrush(QBrush(Qt.GlobalColor.white))
        self.setPen(QPen(Qt.GlobalColor.darkBlue, 2))
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)

        self.label = QGraphicsTextItem(self.person.name, self)
        self.label.setDefaultTextColor(Qt.GlobalColor.black)
        self.label.setFont(QFont("Arial", 10, QFont.Weight.Bold))

        bounds = self.label.boundingRect()
        self.label.setPos((NodeItem.WIDTH - bounds.width()) / 2, (NodeItem.HEIGHT - bounds.height()) / 2)

    def update_style(self, selected=False):
        """Visually mark the selected node with a red outline, otherwise normal blue."""
        if selected:
            self.setPen(QPen(Qt.GlobalColor.red, 3))
        else:
            self.setPen(QPen(Qt.GlobalColor.darkBlue, 2))

    def mousePressEvent(self, event):
        """When user clicks on this person box, notify TreeEditor."""
        super().mousePressEvent(event)
        if callable(self.callback):
            self.callback(self.person)


class PanGraphicsView(QGraphicsView):
    """Custom graphics view that supports panning with right mouse button."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._panning = False
        self._pan_start = None

    def mousePressEvent(self, event):
        """Start panning mode on right-click, otherwise act normally."""
        if event.button() == Qt.MouseButton.RightButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Move the view while right mouse is held down."""
        if self._panning and self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Stop panning when the right mouse button is released."""
        if event.button() == Qt.MouseButton.RightButton and self._panning:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            super().mouseReleaseEvent(event)


class PersonDialog(QDialog):
    """A simple popup dialog that asks for person details."""
    def __init__(self, parent=None, title="New Person", person=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        
        # 1. Create Layouts
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # 2. Add Input Fields
        self.first_name_input = QLineEdit()
        self.last_name_input = QLineEdit()
        self.dob_known_checkbox = QCheckBox("Date of Birth Known")
        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDisplayFormat("yyyy-MM-dd")
        
        form_layout.addRow("First Name:", self.first_name_input)
        form_layout.addRow("Last Name:", self.last_name_input)
        form_layout.addRow("Date of Birth:", self.dob_known_checkbox)
        form_layout.addRow("", self.dob_input)
        
        # 3. Add Standard Buttons (OK/Cancel)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addLayout(form_layout)
        layout.addWidget(buttons)
        
        # Connect checkbox to enable/disable date input
        self.dob_known_checkbox.stateChanged.connect(self.on_dob_known_changed)
        
        # Pre-fill if editing
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
        else:
            self.dob_known_checkbox.setChecked(False)
        
        self.on_dob_known_changed()  # Set initial state

    def on_dob_known_changed(self):
        """Enable or disable the date input based on checkbox."""
        self.dob_input.setEnabled(self.dob_known_checkbox.isChecked())

    def get_data(self):
        """Return the entered form data as a simple dictionary."""
        dob = (self.dob_input.date().toString("yyyy-MM-dd") 
               if self.dob_known_checkbox.isChecked() else "Unknown")
        return {
            "first_name": self.first_name_input.text().strip(),
            "last_name": self.last_name_input.text().strip(),
            "dob": dob
        }


class TreeEditor(QMainWindow):
    """Main application window where you create/modify the family tree graph."""
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Family Tree Editor")
        self.resize(1100, 700)

        self.people = {}
        self.current_person = None
        self.compare_person = None
        self.node_items = {}

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout()
        central_widget.setLayout(self.main_layout)

        self.title_label = QLabel("Family Tree Editor")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        self.main_layout.addWidget(self.title_label)

        top_control = QHBoxLayout()
        self.create_root_button = QPushButton("Create Person (First, Last, D.O.B)")
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

        graph_layout = QHBoxLayout()
        self.scene = QGraphicsScene()
        self.view = PanGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

        graph_layout.addWidget(self.view, stretch=3)

        info_panel = QVBoxLayout()
        self.name_label = QLabel("Name: -")
        self.relations_label = QLabel("Relations: -")
        self.edit_button = QPushButton("Edit Person")
        self.edit_button.clicked.connect(self.edit_current_person)
        info_panel.addWidget(self.name_label)
        info_panel.addWidget(self.relations_label)
        info_panel.addWidget(self.edit_button)
        
        # Add separator and relationship comparison section
        separator1 = QLabel("─" * 40)
        info_panel.addWidget(separator1)
        
        compare_label = QLabel("Relationship Comparison")
        compare_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        info_panel.addWidget(compare_label)
        
        info_panel.addWidget(QLabel("Compare with:"))
        self.compare_person_selector = QComboBox()
        self.compare_person_selector.currentIndexChanged.connect(self.on_compare_person_changed)
        info_panel.addWidget(self.compare_person_selector)
        
        self.blood_relation_label = QLabel("Blood Relation: -")
        self.full_relation_label = QLabel("Full Relation: -")
        self.is_related_label = QLabel("Related: -")
        
        info_panel.addWidget(self.blood_relation_label)
        info_panel.addWidget(self.full_relation_label)
        info_panel.addWidget(self.is_related_label)
        
        info_panel.addStretch(1)

        graph_layout.addLayout(info_panel, stretch=1)

        self.main_layout.addLayout(graph_layout)

        self.buttons_layout = QHBoxLayout()
        self.parent_button = QPushButton("Add Parent")
        self.parent_button.clicked.connect(lambda: self.manage_relationship("parent"))
        self.child_button = QPushButton("Add Child")
        self.child_button.clicked.connect(lambda: self.manage_relationship("child"))
        self.partner_button = QPushButton("Add/Set Partner")
        self.partner_button.clicked.connect(lambda: self.manage_relationship("partner"))

        self.buttons_layout.addWidget(self.parent_button)
        self.buttons_layout.addWidget(self.child_button)
        self.buttons_layout.addWidget(self.partner_button)

        self.main_layout.addLayout(self.buttons_layout)

        self.update_ui_state()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        window_size = min(self.width(), self.height())
        self.title_label.setFont(QFont("Arial", max(18, int(window_size * 0.03)), QFont.Weight.Bold))

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def update_ui_state(self):
        """Refresh the controls and display after data changes."""
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
        """Update the dropdown lists so they reflect all known people."""
        selected_id = self.current_person.id if self.current_person else None
        self.person_selector.blockSignals(True)
        self.person_selector.clear()

        self.person_selector.addItem("Select person", None)
        for p in self.people.values():
            self.person_selector.addItem(f"{p.name} ({p.id[:8]})", p.id)

        if selected_id is not None:
            for i in range(self.person_selector.count()):
                if self.person_selector.itemData(i) == selected_id:
                    self.person_selector.setCurrentIndex(i)
                    break

        self.person_selector.blockSignals(False)
        
        # Also update the compare person selector
        compare_selected_id = None
        if hasattr(self, 'compare_person'):
            compare_selected_id = self.compare_person.id if self.compare_person else None
        
        self.compare_person_selector.blockSignals(True)
        self.compare_person_selector.clear()
        self.compare_person_selector.addItem("Select person to compare", None)
        
        for p in self.people.values():
            self.compare_person_selector.addItem(f"{p.name} ({p.id[:8]})", p.id)
        
        if compare_selected_id is not None:
            for i in range(self.compare_person_selector.count()):
                if self.compare_person_selector.itemData(i) == compare_selected_id:
                    self.compare_person_selector.setCurrentIndex(i)
                    break
        
        self.compare_person_selector.blockSignals(False)
        
        # Trigger update
        self.on_compare_person_changed()

    def on_person_selected(self):
        """Callback for dropdown selection changes."""
        selected_id = self.person_selector.currentData()
        if selected_id and selected_id in self.people:
            self.set_current_person(self.people[selected_id])

    def on_compare_person_changed(self):
        """Callback when comparison person is selected."""
        selected_id = self.compare_person_selector.currentData()
        if selected_id and selected_id in self.people:
            self.compare_person = self.people[selected_id]
        else:
            self.compare_person = None
        self.update_relationship_display()

    def update_relationship_display(self):
        """Update the relationship display between current_person and compare_person."""
        if not self.current_person or not self.compare_person:
            self.blood_relation_label.setText("Blood Relation: -")
            self.full_relation_label.setText("Full Relation: -")
            self.is_related_label.setText("Related: -")
            return
        
        # Check if they're the same person
        if self.current_person is self.compare_person:
            self.blood_relation_label.setText("Blood Relation: Self")
            self.full_relation_label.setText("Full Relation: Self")
            self.is_related_label.setText("Related: Yes (self)")
            return
        
        # Get relationships
        blood_rel = find_blood_relationship(self.current_person, self.compare_person)
        full_rel = find_relationship(self.current_person, self.compare_person)
        is_blood = detect_blood_relation(self.current_person, self.compare_person)
        
        # Format display
        blood_text = blood_rel if blood_rel else "Not related by blood"
        full_text = full_rel if full_rel else "Not related"
        related_status = "Yes" if (blood_rel or full_rel) else "No"
        
        self.blood_relation_label.setText(f"Blood Relation: {blood_text}")
        self.full_relation_label.setText(f"Full Relation: {full_text}")
        self.is_related_label.setText(f"Related: {related_status}")

    def set_current_person(self, person):
        """Mark one person as active and refresh selection highlighting."""
        self.current_person = person
        for node in self.node_items.values():
            node.update_style(selected=(node.person is person))
        self.update_ui_state()

    def display_current_person(self):
        """Display the selected person's name and family relationships in the side panel."""
        if not self.current_person:
            return

        self.name_label.setText(f"Name: {self.current_person.name} | DOB: {self.current_person.dob} | ID: {self.current_person.id[:8]}")

        parents = ", ".join(p.name for p in self.current_person.parents) or "None"
        children = ", ".join(c.name for c in self.current_person.children) or "None"
        partner = self.current_person.partner.name if self.current_person.partner else "None"
        self.relations_label.setText(f"Parents: {parents}\nChildren: {children}\nPartner: {partner}")

    def edit_current_person(self):
        """Open a dialog to edit the currently selected person."""
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
            self.current_person.first_name = data["first_name"]
            self.current_person.last_name = data["last_name"]
            self.current_person.name = f"{data['first_name']} {data['last_name']}".strip()
            self.current_person.dob = data["dob"]
            self.update_ui_state()

    def create_root_person(self):
        """Add the first person when there is no tree yet."""
        new_person = self.create_person_dialog("Root person")
        if new_person:
            self.people[new_person.id] = new_person
            self.set_current_person(new_person)
            self.update_ui_state()

    def create_person_dialog(self, title):
        """Show the dialog and interpret result as a Person object."""
        dialog = PersonDialog(self, title)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()

        if not data["first_name"]:
            data["first_name"] = None
        if not data["last_name"]:
            data["last_name"] = None
        if not data["dob"]:
            data["dob"] = None
        
        return Person(
            first_name=data["first_name"], 
            last_name=data["last_name"], 
            dob=data["dob"]
        )

    def choose_existing_person(self, exclude=None):
        """Ask the user to pick from an existing person (except excluded one)."""
        candidates = [p for p in self.people.values() if p is not exclude]
        if not candidates:
            QMessageBox.information(self, "No Existing Person", "No existing person available. Create a new one instead.")
            return None

        options = [f"{p.name} ({p.id[:8]})" for p in candidates]
        item, ok = QInputDialog.getItem(self, "Choose Person", "Select existing person:", options, editable=False)
        if ok and item:
            for p in candidates:
                if item.startswith(p.name):
                    return p
        return None

    def get_visible_people(self):
        """Compute which people should be shown on the screen.

        This keeps the display focused on the selected person and close relatives.
        When nothing is selected, show the entire tree.
        """
        # If no one is selected, show everyone
        if not self.current_person:
            return set(self.people.values())

        blood_relatives = set()
        
        # Step 1: Find all ancestors of the focus person (trace bloodline UP)
        ancestors = set()
        queue = [self.current_person]
        while queue:
            curr = queue.pop(0)
            if curr not in ancestors:
                ancestors.add(curr)
                queue.extend(curr.parents)

        # Step 2: Find all descendants of all ancestors (trace bloodline DOWN)
        # This naturally captures siblings, aunts, uncles, cousins, etc.
        roots = list(ancestors) if ancestors else [self.current_person]
        queue = roots.copy()
        while queue:
            curr = queue.pop(0)
            if curr not in blood_relatives:
                blood_relatives.add(curr)
                queue.extend(curr.children)

        # Step 3: Apply the strict visibility boundaries
        visible = set()
        for person in blood_relatives:
            visible.add(person)
            visible.update(person.parents) # Parents of blood relatives are allowed
            if person.partner:
                visible.add(person.partner) # Spouses of blood relatives are allowed

        # Focus person's spouse gets special rules: add their parents and siblings
        if self.current_person.partner:
            spouse = self.current_person.partner
            visible.add(spouse)
            visible.update(spouse.parents)
            for p in spouse.parents:
                visible.update(p.children) # Siblings of the spouse
                
        return visible

    # --- Persistence -----------------------------------
    def build_person_data(self, person):
        """Convert one person object into a simple dictionary for saving."""
        return {
            "id": person.id,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "dob": person.dob,
            "parents": [p.id for p in person.parents],
            "children": [c.id for c in person.children],
            "partner": person.partner.id if person.partner else None,
        }

    def to_dict(self):
        """Convert all people in the current tree into one serializable dictionary."""
        return {"people": [self.build_person_data(p) for p in self.people.values()]}

    def serialize_json(self, path):
        """Save the current family tree to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def serialize_xml(self, path):
        """Save the current family tree to an XML file."""
        root = ET.Element("family_tree")
        for person in self.people.values():
            p_elem = ET.SubElement(root, "person", attrib={"id": person.id})
            ET.SubElement(p_elem, "first_name").text = person.first_name
            ET.SubElement(p_elem, "last_name").text = person.last_name
            ET.SubElement(p_elem, "dob").text = person.dob

            parents_elem = ET.SubElement(p_elem, "parents")
            for pid in [p.id for p in person.parents]:
                ET.SubElement(parents_elem, "parent").text = pid

            children_elem = ET.SubElement(p_elem, "children")
            for cid in [c.id for c in person.children]:
                ET.SubElement(children_elem, "child").text = cid

            ET.SubElement(p_elem, "partner").text = person.partner.id if person.partner else ""

        tree = ET.ElementTree(root)
        tree.write(path, encoding="utf-8", xml_declaration=True)

    def load_from_dict(self, data):
        """Restore the in-memory tree from saved data structure."""
        self.people.clear()
        self.current_person = None

        # create persons first
        for p_data in data.get("people", []):
            p = Person(
                first_name=p_data.get("first_name"),
                last_name=p_data.get("last_name"),
                dob=p_data.get("dob"),
                person_id=p_data.get("id"),
            )
            self.people[p.id] = p

        # establish relationships
        for p_data in data.get("people", []):
            p = self.people.get(p_data["id"])
            if not p:
                continue
            for parent_id in p_data.get("parents", []):
                parent = self.people.get(parent_id)
                if parent:
                    p.add_parent(parent)
            for child_id in p_data.get("children", []):
                child = self.people.get(child_id)
                if child:
                    p.add_child(child)
            partner_id = p_data.get("partner")
            if partner_id:
                partner = self.people.get(partner_id)
                if partner:
                    p.set_partner(partner)

        if self.people:
            self.set_current_person(next(iter(self.people.values())))
        self.update_ui_state()

    def deserialize_json(self, path):
        """Load tree from JSON file on disk."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_from_dict(data)

    def deserialize_xml(self, path):
        """Load tree from XML file on disk."""
        tree = ET.parse(path)
        root = tree.getroot()
        data = {"people": []}

        for p_elem in root.findall("person"):
            pid = p_elem.get("id")
            first_name = p_elem.findtext("first_name", "Unnamed")
            last_name = p_elem.findtext("last_name", "Unnamed")
            dob = p_elem.findtext("dob", "Unknown")

            parents = [c.text for c in p_elem.find("parents") or [] if c.text]
            children = [c.text for c in p_elem.find("children") or [] if c.text]
            partner = p_elem.findtext("partner", "")
            partner = partner if partner else None

            data["people"].append({
                "id": pid,
                "first_name": first_name,
                "last_name": last_name,
                "dob": dob,
                "parents": parents,
                "children": children,
                "partner": partner,
            })

        self.load_from_dict(data)

    def save_tree(self):
        """Ask the user for a file path then save the tree."""
        path, selected = QFileDialog.getSaveFileName(
            self,
            "Save Family Tree",
            "family_tree.json",
            "JSON Files (*.json);;XML Files (*.xml)",
        )
        if not path:
            return

        try:
            if path.lower().endswith(".xml") or selected.startswith("XML"):
                self.serialize_xml(path)
            else:
                self.serialize_json(path)
            QMessageBox.information(self, "Save Successful", f"Saved family tree to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save family tree:\n{e}")

    def load_tree(self):
        """Ask the user for a file path then load the tree."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Family Tree",
            "",
            "JSON Files (*.json);;XML Files (*.xml)",
        )
        if not path:
            return

        try:
            if path.lower().endswith(".xml"):
                self.deserialize_xml(path)
            else:
                self.deserialize_json(path)
            QMessageBox.information(self, "Load Successful", f"Loaded family tree from {path}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load family tree:\n{e}")


    def manage_relationship(self, relationship):
        """Handle adding parent, child, or partner for the currently selected person."""
        if not self.current_person:
            return

        choice, ok = QInputDialog.getItem(
            self,
            "Relationship Action",
            "Choose action:",
            ["Create New Person", "Add Existing Person"],
            editable=False,
        )

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
            self.current_person.add_parent(target)
            target.add_child(self.current_person) # Ensure bidirectional link
            
            # If the person now has 2 parents, automatically make them partners
            if len(self.current_person.parents) == 2:
                p1, p2 = list(self.current_person.parents)[:2]
                p1.set_partner(p2)
                p2.set_partner(p1)
                
        elif relationship == "child":
            self.current_person.add_child(target)
            target.add_parent(self.current_person)
            
            # If the current person has a partner, add the child to the partner too
            if self.current_person.partner:
                self.current_person.partner.add_child(target)
                target.add_parent(self.current_person.partner)
                
        elif relationship == "partner":
            self.current_person.set_partner(target)
            target.set_partner(self.current_person) # Ensure bidirectional link

        self.set_current_person(self.current_person)

    def refresh_graph(self):
        """Rebuild the visual family tree prioritizing the current person with strict Left/Right segregation."""
        import collections
        
        self.scene.clear()
        self.node_items = {}

        if not self.people:
            self.scene.addText("Create or load a person to start your tree.")
            return

        visible_people = self.get_visible_people()
        if not visible_people:
            return

        # Identify the priority center
        center_person = self.current_person if self.current_person in visible_people else visible_people[0]

        # --- 1. Group Families into Units ---
        person_to_unit = {}
        units = set()
        for p in visible_people:
            if p.id in person_to_unit: continue
            if p.partner and p.partner in visible_people:
                unit = tuple(sorted([p, p.partner], key=lambda x: x.id))
                person_to_unit[p.id] = unit
                person_to_unit[p.partner.id] = unit
                units.add(unit)
            else:
                unit = (p,)
                person_to_unit[p.id] = unit
                units.add(unit)

        # Spacing configuration
        h_space = 180
        v_space = 150
        padding = 50 # Minimum gap between different family blocks

        def get_unit_width(u):
            return len(u) * h_space

        # Tracking state for the outward placement
        placed_units = set()
        unit_positions = {} # unit -> (center_x, y)
        level_spans = collections.defaultdict(list) # y -> list of (left_x, right_x, unit)

        def resolve_overlap(u, ideal_x, y, tag):
            """Finds the closest available spot, forcing strict Left/Right outward movement based on lineage tag."""
            u_width = get_unit_width(u)
            half_w = u_width / 2
            
            # Enforce strict push directions: -1 = ONLY Left, 1 = ONLY Right, 0 = Closest outward
            if tag == -1:
                direction = -1
            elif tag == 1:
                direction = 1
            else:
                direction = 1 if ideal_x >= 0 else -1

            current_x = ideal_x

            while True:
                left_edge = current_x - half_w
                right_edge = current_x + half_w
                overlapped = False

                for (span_l, span_r, placed_u) in level_spans[y]:
                    if not (right_edge + padding <= span_l or left_edge - padding >= span_r):
                        overlapped = True
                        # Push strictly outwards based on the assigned family side
                        if direction == 1:
                            current_x = span_r + padding + half_w
                        else:
                            current_x = span_l - padding - half_w
                        break

                if not overlapped:
                    return current_x

        # --- 2. BFS Outward Placement with Strict Lineage Tagging ---
        # Queue format: (unit, ideal_x, y_level, lineage_tag)
        # Tag Key: 0 = Center Trunk, -1 = Strict Left (Father's side), 1 = Strict Right (Mother's side)
        queue = collections.deque()
        unprocessed_units = set(units)
        
        center_unit = person_to_unit[center_person.id]
        queue.append((center_unit, 0, 0, 0)) 

        current_disjoint_offset = 0

        while unprocessed_units:
            # Handle completely disconnected family trees
            if not queue:
                next_unit = unprocessed_units.pop()
                unprocessed_units.add(next_unit)
                current_disjoint_offset += 1000 
                queue.append((next_unit, current_disjoint_offset, 0, 1))

            while queue:
                u, ideal_x, y, tag = queue.popleft()
                if u in placed_units:
                    continue

                # Lock in position, pushing out strictly to their family's side
                final_x = resolve_overlap(u, ideal_x, y, tag)
                unit_positions[u] = (final_x, y)
                
                half_w = get_unit_width(u) / 2
                level_spans[y].append((final_x - half_w, final_x + half_w, u))
                
                placed_units.add(u)
                unprocessed_units.remove(u)

                # --- Queue Parents (Upward) ---
                # If we are on the center trunk, we need to split the parents into Left and Right branches
                if tag == 0 and len(u) == 2:
                    p1, p2 = u[0], u[1]
                    p1_parents = list(set(person_to_unit[par.id] for par in p1.parents if par in visible_people))
                    p2_parents = list(set(person_to_unit[par.id] for par in p2.parents if par in visible_people))
                    
                    for pu in p1_parents:
                        if pu not in placed_units:
                            queue.append((pu, final_x - h_space, y - v_space, -1)) # Assign Left Lineage
                    for pu in p2_parents:
                        if pu not in placed_units:
                            queue.append((pu, final_x + h_space, y - v_space, 1))  # Assign Right Lineage
                
                elif tag == 0 and len(u) == 1:
                    p1 = u[0]
                    p_units = list(set(person_to_unit[par.id] for par in p1.parents if par in visible_people))
                    p_units.sort(key=lambda x: x[0].id)
                    
                    if len(p_units) == 1:
                        queue.append((p_units[0], final_x, y - v_space, 0))
                    elif len(p_units) >= 2:
                        queue.append((p_units[0], final_x - h_space, y - v_space, -1))
                        queue.append((p_units[1], final_x + h_space, y - v_space, 1))
                
                else:
                    # Maintain the assigned Tag (Left stays Left, Right stays Right)
                    parents_of_u = set()
                    for p in u:
                        for par in p.parents:
                            if par in visible_people:
                                parents_of_u.add(person_to_unit[par.id])
                    
                    sorted_parents = sorted(list(parents_of_u), key=lambda x: x[0].id)
                    if tag == -1:
                        parent_offset = final_x - h_space
                        for pu in sorted_parents:
                            if pu not in placed_units:
                                queue.append((pu, parent_offset, y - v_space, -1))
                                parent_offset -= h_space
                    elif tag == 1:
                        parent_offset = final_x + h_space
                        for pu in sorted_parents:
                            if pu not in placed_units:
                                queue.append((pu, parent_offset, y - v_space, 1))
                                parent_offset += h_space

                # --- Queue Children (Downward) ---
                children_of_u = set()
                for p in u:
                    for child in p.children:
                        if child in visible_people:
                            children_of_u.add(person_to_unit[child.id])

                if children_of_u:
                    sorted_children = sorted(list(children_of_u), key=lambda x: x[0].id)
                    
                    if tag == -1:
                        child_offset = final_x - h_space
                        for cu in sorted_children:
                            if cu not in placed_units:
                                queue.append((cu, child_offset, y + v_space, -1))
                                child_offset -= h_space
                    elif tag == 1:
                        child_offset = final_x + h_space
                        for cu in sorted_children:
                            if cu not in placed_units:
                                queue.append((cu, child_offset, y + v_space, 1))
                                child_offset += h_space
                    else:
                        child_offset = final_x - (len(sorted_children) - 1) * (h_space) / 2
                        for cu in sorted_children:
                            if cu not in placed_units:
                                queue.append((cu, child_offset, y + v_space, 0))
                                child_offset += h_space * 1.5

        # --- 3. Apply Final Positions to Node Items ---
        for u, (center_x, y) in unit_positions.items():
            if len(u) == 1:
                p = u[0]
                node = NodeItem(p, callback=self.set_current_person)
                node.setPos(center_x, y)
                self.scene.addItem(node)
                self.node_items[p.id] = node
            else:
                p1, p2 = u[0], u[1]
                node1 = NodeItem(p1, callback=self.set_current_person)
                node2 = NodeItem(p2, callback=self.set_current_person)
                
                node1.setPos(center_x - (h_space * 0.4), y)
                node2.setPos(center_x + (h_space * 0.4), y)
                
                self.scene.addItem(node1)
                self.scene.addItem(node2)
                
                self.node_items[p1.id] = node1
                self.node_items[p2.id] = node2

        # --- 4. DRAWING LOGIC (Lines & Relations) ---
        drawn_partner_lines = set()
        partner_midpoints = {}
        
        for person in visible_people:
            if person.partner and person.partner in visible_people:
                pair_key = frozenset([person.id, person.partner.id])
                if pair_key not in drawn_partner_lines:
                    drawn_partner_lines.add(pair_key)
                    p_item = self.node_items.get(person.id)
                    partner_item = self.node_items.get(person.partner.id)
                    
                    if p_item and partner_item:
                        p_center = p_item.sceneBoundingRect().center()
                        partner_center = partner_item.sceneBoundingRect().center()
                        
                        partner_line = self.scene.addLine(
                            p_center.x(), p_center.y(), 
                            partner_center.x(), partner_center.y(), 
                            QPen(Qt.GlobalColor.blue, 2, Qt.PenStyle.DashLine)
                        )
                        partner_line.setZValue(-1)
                        
                        mid_x = (p_center.x() + partner_center.x()) / 2
                        mid_y = (p_center.y() + partner_center.y()) / 2
                        partner_midpoints[pair_key] = (mid_x, mid_y)

        drawn_child_lines = set()

        for person in visible_people:
            p_item = self.node_items.get(person.id)
            if not p_item:
                continue
                
            for child in person.children:
                if child not in visible_people:
                    continue
                
                child_item = self.node_items.get(child.id)
                if not child_item:
                    continue
                    
                c_center = child_item.sceneBoundingRect().center()
                child_top_y = c_center.y() - NodeItem.HEIGHT / 2
                
                is_joint_child = False
                pair_key = None
                
                if person.partner and person.partner in visible_people and child in person.partner.children:
                    is_joint_child = True
                    pair_key = frozenset([person.id, person.partner.id])

                if is_joint_child and pair_key in partner_midpoints:
                    if (pair_key, child.id) not in drawn_child_lines:
                        drawn_child_lines.add((pair_key, child.id))
                        mid_x, mid_y = partner_midpoints[pair_key]
                        
                        line = self.scene.addLine(
                            mid_x, mid_y, 
                            c_center.x(), child_top_y, 
                            QPen(Qt.GlobalColor.darkGreen, 2)
                        )
                        line.setZValue(-1)
                else:
                    parent_key = (person.id, child.id)
                    if parent_key not in drawn_child_lines:
                        drawn_child_lines.add(parent_key)
                        p_center = p_item.sceneBoundingRect().center()
                        parent_bottom_y = p_center.y() + NodeItem.HEIGHT / 2
                        
                        line = self.scene.addLine(
                            p_center.x(), parent_bottom_y, 
                            c_center.x(), child_top_y, 
                            QPen(Qt.GlobalColor.darkGreen, 2)
                        )
                        line.setZValue(-1)

        # Apply final styling and centering
        if self.current_person and self.current_person.id in self.node_items:
            self.node_items[self.current_person.id].update_style(True)

        bounds = self.scene.itemsBoundingRect().adjusted(-100, -100, 100, 100)
        self.scene.setSceneRect(bounds)

        if self.current_person and self.current_person.id in self.node_items:
            self.view.centerOn(self.node_items[self.current_person.id])


    def find_root_person(self, visible_people):
        """Choose an ancestor with no parents in the visible subset to start level computations."""
        candidates = [p for p in visible_people if not any(parent in visible_people for parent in p.parents)]
        if candidates:
            return candidates[0]
        return next(iter(visible_people))

    def compute_levels(self, root, visible_people):
        """Assign each person to a row number used for layout (generation levels)."""
        levels = {}
        visited = set()
        queue = [(root, 0)]

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
    app = QApplication(sys.argv)
    window = TreeEditor()
    window.show()
    sys.exit(app.exec())
