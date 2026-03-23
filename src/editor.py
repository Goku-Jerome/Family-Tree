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
    QVBoxLayout    
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QFont, QPen, QBrush, QPainter
from person import Person


class NodeItem(QGraphicsRectItem):
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
        if selected:
            self.setPen(QPen(Qt.GlobalColor.red, 3))
        else:
            self.setPen(QPen(Qt.GlobalColor.darkBlue, 2))

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if callable(self.callback):
            self.callback(self.person)


class PanGraphicsView(QGraphicsView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._panning = False
        self._pan_start = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self._panning:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            super().mouseReleaseEvent(event)


class PersonDialog(QDialog):
    def __init__(self, parent=None, title = "New Person"):
        super().__init__(parent)
        self.setWindowTitle(title)
        
        # 1. Create Layouts
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # 2. Add Input Fields
        self.first_name_input = QLineEdit()
        self.last_name_input = QLineEdit()
        self.dob_input = QLineEdit()
        self.dob_input.setPlaceholderText("YYYY-MM-DD or text")
        
        form_layout.addRow("First Name:", self.first_name_input)
        form_layout.addRow("Last Name:", self.last_name_input)
        form_layout.addRow("Date of Birth:", self.dob_input)
        
        # 3. Add Standard Buttons (OK/Cancel)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

    def get_data(self):
        return {
            "first_name": self.first_name_input.text().strip(),
            "last_name": self.last_name_input.text().strip(),
            "dob": self.dob_input.text().strip() or "Unknown"
        }


class TreeEditor(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Family Tree Editor")
        self.resize(1100, 700)

        self.people = {}
        self.current_person = None
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
        info_panel.addWidget(self.name_label)
        info_panel.addWidget(self.relations_label)
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
        has_person = bool(self.people)
        self.person_selector.setEnabled(has_person)
        self.parent_button.setEnabled(self.current_person is not None)
        self.child_button.setEnabled(self.current_person is not None)
        self.partner_button.setEnabled(self.current_person is not None)

        self.refresh_person_selector()
        self.refresh_graph()

        if self.current_person:
            self.display_current_person()
        else:
            self.name_label.setText("Name: -")
            self.relations_label.setText("Relations: -")

    def refresh_person_selector(self):
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

    def on_person_selected(self):
        selected_id = self.person_selector.currentData()
        if selected_id and selected_id in self.people:
            self.set_current_person(self.people[selected_id])

    def set_current_person(self, person):
        self.current_person = person
        for node in self.node_items.values():
            node.update_style(selected=(node.person is person))
        self.update_ui_state()

    def display_current_person(self):
        if not self.current_person:
            return

        self.name_label.setText(f"Name: {self.current_person.name} | DOB: {self.current_person.dob} | ID: {self.current_person.id[:8]}")

        parents = ", ".join(p.name for p in self.current_person.parents) or "None"
        children = ", ".join(c.name for c in self.current_person.children) or "None"
        partner = self.current_person.partner.name if self.current_person.partner else "None"
        self.relations_label.setText(f"Parents: {parents}\nChildren: {children}\nPartner: {partner}")

    def create_root_person(self):
        new_person = self.create_person_dialog("Root person")
        if new_person:
            self.people[new_person.id] = new_person
            self.set_current_person(new_person)
            self.update_ui_state()

    def create_person_dialog(self, title):
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
        return {"people": [self.build_person_data(p) for p in self.people.values()]}

    def serialize_json(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def serialize_xml(self, path):
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
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_from_dict(data)

    def deserialize_xml(self, path):
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
        self.scene.clear()
        self.node_items = {}

        if not self.people:
            self.scene.addText("Create or load a person to start your tree.")
            return

        # Fetch pruned list
        visible_people = self.get_visible_people()
        if not visible_people:
            return

        root = self.find_root_person(visible_people)
        order = self.compute_levels(root, visible_people)

        # --- 1. Group Families & Build Strict Hierarchy ---
        # Group partners into unbreakable Family Units (Singles or Couples)
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

        # Map actual children to these units
        unit_children_raw = {u: set() for u in units}
        for u in units:
            for p in u:
                for child in p.children:
                    if child in visible_people:
                        unit_children_raw[u].add(person_to_unit[child.id])
                        
        # Determine average level for each unit to process top-down
        unit_levels = {}
        for u in units:
            lvl = int(sum(next((l for l, ps in order.items() if p in ps), 0) for p in u) / len(u))
            unit_levels[u] = lvl

        # Convert the complex web into a strict Spanning Tree to prevent crossing
        layout_children = {u: [] for u in units}
        claimed = set()
        
        # Claim children generation by generation (top-down)
        for lvl in sorted(set(unit_levels.values())):
            lvl_units = sorted([u for u, l in unit_levels.items() if l == lvl], key=lambda u: u[0].id)
            for u in lvl_units:
                kids = sorted(list(unit_children_raw[u]), key=lambda cu: cu[0].id)
                for child_unit in kids:
                    if child_unit not in claimed:
                        layout_children[u].append(child_unit)
                        claimed.add(child_unit)

        # --- 2. Calculate Required Widths (Bottom-Up) ---
        h_space = 180
        v_space = 150
        unit_widths = {}
        
        # Start from the youngest generation and work up to the oldest
        for lvl in sorted(set(unit_levels.values()), reverse=True):
            lvl_units = [u for u, l in unit_levels.items() if l == lvl]
            for u in lvl_units:
                children = layout_children[u]
                min_width = len(u) * h_space
                if not children:
                    unit_widths[u] = min_width
                else:
                    # A parent's block must be at least as wide as all their descendants combined
                    children_width = sum(unit_widths.get(c, len(c)*h_space) for c in children)
                    padding = (len(children) - 1) * 40 # 40px guaranteed gap between sibling branches
                    unit_widths[u] = max(min_width, children_width + padding)

        # --- 3. Assign Absolute X Positions (Top-Down) ---
        unit_x = {}
        
        # Identify the oldest ancestors (roots)
        roots = [u for u in units if u not in claimed]
        roots.sort(key=lambda u: u[0].id)
        
        current_start_x = 0
        
        def assign_x(u, start_x):
            my_width = unit_widths[u]
            unit_x[u] = start_x + (my_width / 2) # Center this family in their dedicated block
            
            child_start_x = start_x
            
            # If the parents are physically wider than their kids, center the kids under the parents
            children = layout_children[u]
            if children:
                children_total_width = sum(unit_widths[c] for c in children) + (len(children) - 1) * 40
                if my_width > children_total_width:
                    child_start_x = start_x + (my_width - children_total_width) / 2
            
            # Recursively assign dedicated column spaces to children
            for child in children:
                assign_x(child, child_start_x)
                child_start_x += unit_widths[child] + 40

        for r in roots:
            assign_x(r, current_start_x)
            current_start_x += unit_widths[r] + 100 # 100px gap if multiple separate family trees are loaded

        # --- 4. Apply Final Positions to Nodes ---
        for level, persons in order.items():
            for p in persons:
                u = person_to_unit[p.id]
                center_x = unit_x.get(u, 0)
                
                if len(u) == 1:
                    x = center_x
                else:
                    # --- Bloodline Pull Logic ---
                    # Orient partners so they face their own side of the family
                    p1, p2 = u[0], u[1]
                    
                    def get_pull(person):
                        parents_in_view = [par for par in person.parents if par in visible_people]
                        if parents_in_view:
                            # Calculate the average X position of this person's parents
                            return sum(unit_x.get(person_to_unit[par.id], center_x) for par in parents_in_view) / len(parents_in_view)
                        # If no parents are visible, neutral pull
                        return center_x
                        
                    pull1 = get_pull(p1)
                    pull2 = get_pull(p2)
                    
                    # Sort left/right based on parent locations
                    if pull1 != pull2:
                        left_p = p1 if pull1 < pull2 else p2
                    else:
                        # Fallback to ID if neither has visible parents to anchor to
                        left_p = p1 if p1.id < p2.id else p2
                        
                    # Apply the left/right offset based on the sorting
                    if p == left_p:
                        x = center_x - (h_space * 0.4)
                    else:
                        x = center_x + (h_space * 0.4)
                
                y = level * v_space
                
                node = NodeItem(p, callback=self.set_current_person)
                node.setPos(x, y)
                self.scene.addItem(node)
                self.node_items[p.id] = node
        # --- 3. DRAWING LOGIC (Lines & Relations - Filtered) ---
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
                        
                        # Store the line in a variable and set its Z-value to -1
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

        if self.current_person and self.current_person.id in self.node_items:
            self.node_items[self.current_person.id].update_style(True)

        bounds = self.scene.itemsBoundingRect().adjusted(-100, -100, 100, 100)
        self.scene.setSceneRect(bounds)

        if self.current_person and self.current_person.id in self.node_items:
            self.view.centerOn(self.node_items[self.current_person.id])


    def find_root_person(self, visible_people):
        candidates = [p for p in visible_people if not any(parent in visible_people for parent in p.parents)]
        if candidates:
            return candidates[0]
        return next(iter(visible_people))

    def compute_levels(self, root, visible_people):
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
