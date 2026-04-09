# editor.py
# This module is the main family tree editor window and drawing engine.
# It creates a visual graph of people with interactive selection and actions.

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
    QVBoxLayout,
    QDateEdit,
    QCheckBox,
    QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QTimer
from PyQt6.QtGui import QFont, QPen, QBrush, QPainter, QColor
from person import Person
from relation import find_relationship_bfs, get_relationship_title
import options


# ─────────────────────────────────────────────
#  Layout constants  (Family Echo proportions)
# ─────────────────────────────────────────────
NODE_W          = 140   # card width
NODE_H          =  56   # card height
H_GAP           =  30   # minimum horizontal gap between cards on same row
COUPLE_GAP      =  18   # gap between two partners in a couple
GEN_H_GAP       = 100   # vertical gap between generations
SUBTREE_PAD     =  12   # extra horizontal padding between independent sub-trees

# Colours (Family Echo palette)
COL_MALE        = QColor("#d6e8f7")   # soft blue
COL_FEMALE      = QColor("#fce4ec")   # soft pink
COL_OTHER       = QColor("#f3e5f5")   # lavender
COL_SELECTED_BG = QColor("#fff9c4")   # yellow highlight
COL_BORDER_NORM = QColor("#546e7a")
COL_BORDER_SEL  = QColor("#e53935")   # red when selected
COL_LINE_COUPLE = QColor("#1565c0")   # dark blue  – partner line
COL_LINE_CHILD  = QColor("#2e7d32")   # dark green – parent→child


class NodeItem(QGraphicsRectItem):
    """A single rounded rectangle representing one person."""
    def __init__(self, person, callback):
        super().__init__(0, 0, NODE_W, NODE_H)
        self.person   = person
        self.callback = callback
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._selected = False
        self._apply_style()

        # Name label (two lines: first / last)
        display = person.name
        self.label = QGraphicsTextItem(display, self)
        self.label.setDefaultTextColor(Qt.GlobalColor.black)
        self.label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.label.setTextWidth(NODE_W - 8)
        self.label.setPos(4, (NODE_H - self.label.boundingRect().height()) / 2)

        # Small DOB sub-label
        if person.dob and person.dob != "Unknown":
            dob_label = QGraphicsTextItem(person.dob, self)
            dob_label.setDefaultTextColor(QColor("#555555"))
            dob_label.setFont(QFont("Arial", 7))
            dob_label.setPos(4, NODE_H - 16)

    def _bg_colour(self):
        if self._selected:
            return COL_SELECTED_BG
        g = str(self.person.gender or "").lower()
        if g.startswith("m"):   return COL_MALE
        if g.startswith("f"):   return COL_FEMALE
        return COL_OTHER

    def _apply_style(self):
        self.setBrush(QBrush(self._bg_colour()))
        pen_col   = COL_BORDER_SEL if self._selected else COL_BORDER_NORM
        pen_width = 3             if self._selected else 1.5
        self.setPen(QPen(pen_col, pen_width))

    def update_style(self, selected=False):
        self._selected = selected
        self._apply_style()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if callable(self.callback):
            self.callback(self.person)


class PanGraphicsView(QGraphicsView):
    """Right-click panning."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._panning   = False
        self._pan_start = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._panning   = True
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
            self._panning   = False
            self._pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class PersonDialog(QDialog):
    def __init__(self, parent=None, title="New Person", person=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout      = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.first_name_input = QLineEdit()
        self.last_name_input  = QLineEdit()
        self.dob_known_checkbox = QCheckBox("Date of Birth Known")
        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDisplayFormat("yyyy-MM-dd")

        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Male", "Female", "Other"])
        self.gender_combo.currentIndexChanged.connect(self.on_gender_changed)

        self.other_gender_input = QLineEdit()
        self.other_gender_input.setPlaceholderText("Please specify...")
        self.other_gender_input.setVisible(False)

        form_layout.addRow("First Name:",    self.first_name_input)
        form_layout.addRow("Last Name:",     self.last_name_input)
        form_layout.addRow("Gender:",        self.gender_combo)
        form_layout.addRow("",               self.other_gender_input)
        form_layout.addRow("Date of Birth:", self.dob_known_checkbox)
        form_layout.addRow("",               self.dob_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form_layout)
        layout.addWidget(buttons)

        self.dob_known_checkbox.stateChanged.connect(self.on_dob_known_changed)

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
                if g.startswith('m'):   self.gender_combo.setCurrentIndex(0)
                elif g.startswith('f'): self.gender_combo.setCurrentIndex(1)
                else:
                    self.gender_combo.setCurrentIndex(2)
                    self.other_gender_input.setText(person.gender)
        else:
            self.dob_known_checkbox.setChecked(False)

        self.on_dob_known_changed()
        self.on_gender_changed()

    def on_dob_known_changed(self):
        self.dob_input.setEnabled(self.dob_known_checkbox.isChecked())

    def on_gender_changed(self):
        self.other_gender_input.setVisible(self.gender_combo.currentText() == "Other")

    def get_data(self):
        dob = (self.dob_input.date().toString("yyyy-MM-dd")
               if self.dob_known_checkbox.isChecked() else "Unknown")
        gs = self.gender_combo.currentText()
        if gs == "Other" and self.other_gender_input.text().strip():
            gender = self.other_gender_input.text().strip()
        elif gs == "Male":   gender = "Male"
        elif gs == "Female": gender = "Female"
        else:                gender = None
        return {
            "first_name": self.first_name_input.text().strip(),
            "last_name":  self.last_name_input.text().strip(),
            "dob":        dob,
            "gender":     gender,
        }


# ══════════════════════════════════════════════════════════════════
#  Family Echo–style layout engine
# ══════════════════════════════════════════════════════════════════

class FamilyUnit:
    """One 'box' in the layout: either a single person or a couple."""
    def __init__(self, members):
        self.members   = list(members)   # 1 or 2 Person objects
        self.x         = 0.0             # centre-x of the unit
        self.y         = 0.0             # top-y of the unit
        self.width     = self._calc_width()

    def _calc_width(self):
        n = len(self.members)
        return NODE_W * n + (COUPLE_GAP if n == 2 else 0)

    @property
    def left(self):  return self.x - self.width / 2
    @property
    def right(self): return self.x + self.width / 2

    def top_centre(self):
        """Centre-x, top-y  (used as anchor for parent lines going down)."""
        return (self.x, self.y)

    def bottom_centre(self):
        """Centre-x, bottom-y  (used as anchor for child lines going up)."""
        return (self.x, self.y + NODE_H)

    def couple_mid_y(self):
        """Y of the horizontal couple line (mid-height of the cards)."""
        return self.y + NODE_H / 2


def _build_units(visible_people, focus=None):
    """Group visible people into FamilyUnits (couples share a unit).
    
    When focus is given, couple units that are direct parents of the focus
    have their members ordered so that focus.parents[0] is members[0] —
    this ensures the paternal line consistently goes left in the layout.
    """
    assigned = set()
    units    = []
    for p in visible_people:
        if p.id in assigned:
            continue
        if p.partner and p.partner in visible_people and p.partner.id not in assigned:
            # Determine canonical order: if one of these is focus.parents[0], put them first
            p1, p2 = p, p.partner
            if focus is not None and len(focus.parents) >= 2:
                if p2 is focus.parents[0] and p1 is focus.parents[1]:
                    p1, p2 = p2, p1  # swap so parents[0] is members[0]
            unit = FamilyUnit([p1, p2])
            assigned.add(p.id)
            assigned.add(p.partner.id)
        else:
            unit = FamilyUnit([p])
            assigned.add(p.id)
        units.append(unit)
    return units


def _assign_generations(visible_people, focus):
    """
    BFS from focus person outward.
    Returns  gen_map: person -> int   (negative = older, positive = younger)
    """
    gen_map = {focus: 0}
    queue   = collections.deque([focus])
    while queue:
        p   = queue.popleft()
        lvl = gen_map[p]
        for par in p.parents:
            if par in visible_people and par not in gen_map:
                gen_map[par] = lvl - 1
                queue.append(par)
        for ch in p.children:
            if ch in visible_people and ch not in gen_map:
                gen_map[ch] = lvl + 1
                queue.append(ch)
        if p.partner and p.partner in visible_people and p.partner not in gen_map:
            gen_map[p.partner] = lvl
            queue.append(p.partner)
    # Anything not reached yet (disconnected segments): attach at gen 0
    for p in visible_people:
        if p not in gen_map:
            gen_map[p] = 0
    return gen_map


def _layout_units(units, gen_map, focus=None):
    """
    Focus-centred bidirectional layout.

    Strategy
    --------
    • The focus person's unit is anchored at x = 0.
    • Their children (and descendants) are spread symmetrically *below* them,
      exactly as before.
    • Their parents are split LEFT / RIGHT:
        – parent[0]'s entire ancestor subtree goes to the LEFT  (negative x)
        – parent[1]'s entire ancestor subtree goes to the RIGHT (positive x)
      Each parent subtree is recursively laid out the same way: a parent's
      own parents split left/right above them.
    • Siblings of the focus person (and their cousins etc.) are children of
      their shared parent unit, so they fall naturally below that parent unit
      after the parent has been placed.
    • Any units not reachable from the focus (disconnected sub-trees) are
      appended to the right.
    """
    # ── helpers ────────────────────────────────────────────────────
    p2u = {}
    for u in units:
        for m in u.members:
            p2u[m] = u

    def unit_gen(u):
        gens = [gen_map.get(m, 0) for m in u.members]
        return round(sum(gens) / len(gens))

    u_gen   = {u: unit_gen(u) for u in units}
    min_gen = min(u_gen.values())

    def child_units(u):
        cu = set()
        for m in u.members:
            for ch in m.children:
                if ch in p2u:
                    cu.add(p2u[ch])
        return [c for c in cu if u_gen[c] > u_gen[u]]

    def parent_units(u):
        pu = set()
        for m in u.members:
            for par in m.parents:
                if par in p2u:
                    pu.add(p2u[par])
        return [p for p in pu if u_gen[p] < u_gen[u]]

    # ── subtree widths (downward, used for children) ────────────────
    down_cache = {}
    def down_width(u):
        if u in down_cache:
            return down_cache[u]
        children = child_units(u)
        if not children:
            w = u.width + SUBTREE_PAD
        else:
            w = max(u.width + SUBTREE_PAD,
                    sum(down_width(c) for c in children))
        down_cache[u] = w
        return w

    # ── ancestor widths (upward, used for parents) ─────────────────
    # The "ancestor subtree width" of a unit is the total horizontal space
    # needed by itself plus everything above it.
    up_cache = {}
    def up_width(u):
        """Width needed by u and ALL its ancestors."""
        if u in up_cache:
            return up_cache[u]
        parents = parent_units(u)
        if not parents:
            w = u.width + SUBTREE_PAD
        else:
            w = max(u.width + SUBTREE_PAD,
                    sum(up_width(p) for p in parents))
        up_cache[u] = w
        return w

    # ── placement state ─────────────────────────────────────────────
    placed = set()
    u_x    = {}
    u_y    = {}

    def y_for_gen(g):
        return (g - min_gen) * (NODE_H + GEN_H_GAP)

    # ── place children symmetrically below a unit ───────────────────
    def place_children(u):
        children = [c for c in child_units(u) if c not in placed]
        if not children:
            return
        total_w  = sum(down_width(c) for c in children)
        x_cursor = u_x[u] - total_w / 2
        for c in children:
            sw  = down_width(c)
            cx  = x_cursor + sw / 2
            if c not in placed:
                u_x[c] = cx
                u_y[c] = y_for_gen(u_gen[c])
                placed.add(c)
            place_children(c)
            x_cursor += sw

    # ── place parents split left/right above a unit ─────────────────
    def ensure_left_member(u, left_hint):
        """Reorder u.members so left_hint (or their child) is members[0]."""
        if len(u.members) < 2:
            return
        if left_hint is None:
            return
        # left_hint is a Person who should be on the left side of this unit.
        # If they're members[1], swap.
        if u.members[1] is left_hint:
            u.members[0], u.members[1] = u.members[1], u.members[0]

    def anchored_parent_x(parent_unit):
        child_positions = [u_x[c] for c in child_units(parent_unit) if c in u_x]
        if child_positions:
            return sum(child_positions) / len(child_positions)
        return None

    def place_parents(u, visited=None):
        """
        Place all parent units above u.
        """
        if visited is None:
            visited = set()
        if u in visited:
            return
        visited.add(u)

        parents = [p for p in parent_units(u) if p not in placed]
        if not parents:
            return

        if len(parents) == 1:
            p = parents[0]
            anchor_x = anchored_parent_x(p)
            u_x[p] = anchor_x if anchor_x is not None else u_x[u]
            u_y[p] = y_for_gen(u_gen[p])
            placed.add(p)
            place_children(p)
            place_parents(p, visited)
            return

        member_left  = u.members[0] if len(u.members) >= 1 else None
        member_right = u.members[1] if len(u.members) >= 2 else None

        def parent_side(pu):
            is_right = member_right is not None and any(m in member_right.parents for m in pu.members)
            is_left  = member_left  is not None and any(m in member_left.parents  for m in pu.members)
            if is_right and not is_left:
                return 'right'
            return 'left'

        left_parents  = [p for p in parents if parent_side(p) == 'left']
        right_parents = [p for p in parents if parent_side(p) == 'right']

        # Place any anchored parent units first so they remain centered above their already-positioned children.
        for p in left_parents + right_parents:
            anchor_x = anchored_parent_x(p)
            if anchor_x is not None:
                u_x[p] = anchor_x
                u_y[p] = y_for_gen(u_gen[p])
                placed.add(p)

        def place_side(side_parents, direction):
            if not side_parents:
                return
            x_cursor = u_x[u]
            if direction == -1:
                x_cursor = u_x[u]
            for p in side_parents:
                if p in u_x:
                    continue
                width = max(p.width + SUBTREE_PAD, NODE_W)
                if direction == -1:
                    x_cursor -= width / 2
                    u_x[p] = x_cursor
                    x_cursor -= width / 2 + H_GAP
                else:
                    x_cursor += width / 2
                    u_x[p] = x_cursor
                    x_cursor += width / 2 + H_GAP
                u_y[p] = y_for_gen(u_gen[p])
                placed.add(p)

        place_side(left_parents, -1)
        place_side(right_parents, +1)

        for p in left_parents + right_parents:
            place_children(p)
            place_parents(p, visited)

    # ── seed: place the focus unit at x=0 ───────────────────────────
    focus_unit = None
    if focus is not None and focus in p2u:
        focus_unit = p2u[focus]

    if focus_unit is None:
        # Fall back: pick the unit whose members have gen closest to 0
        focus_unit = min(units, key=lambda u: abs(unit_gen(u)))

    u_x[focus_unit] = 0.0
    u_y[focus_unit] = y_for_gen(u_gen[focus_unit])
    placed.add(focus_unit)

    # Spread focus unit's children below it
    place_children(focus_unit)

    # Spread parents (and their ancestors) above it.
    # left_hint = focus's first listed parent -> their parent unit goes LEFT.
    place_parents(focus_unit)

    # ── handle any unplaced units (disconnected) ────────────────────
    # Find rightmost x used so far
    if u_x:
        right_edge = max(u_x[u] + u.width / 2 for u in placed)
    else:
        right_edge = 0.0

    orphan_x = right_edge + 100
    for u in units:
        if u not in placed:
            u_x[u] = orphan_x
            u_y[u] = y_for_gen(u_gen[u])
            placed.add(u)
            place_children(u)
            place_parents(u)
            orphan_x += down_width(u) + 60

    # ── Push overlapping units on same row apart ───────────────────
    # Sort per generation row and nudge apart.
    # Two passes: left-to-right (push right) then right-to-left (push left)
    # so the layout stays balanced around the focus x=0 anchor.
    rows = collections.defaultdict(list)
    for u in units:
        rows[u_gen[u]].append(u)

    for gen_row in rows.values():
        if not gen_row:
            continue
        orig_center = sum(u_x[u] for u in gen_row) / len(gen_row)
        gen_row.sort(key=lambda u: u_x[u])
        # Pass 1: push overlapping units rightward
        for i in range(1, len(gen_row)):
            prev = gen_row[i - 1]
            curr = gen_row[i]
            min_cx = u_x[prev] + prev.width / 2 + H_GAP + curr.width / 2
            if u_x[curr] < min_cx:
                shift = min_cx - u_x[curr]
                for j in range(i, len(gen_row)):
                    u_x[gen_row[j]] += shift
        # Pass 2: push overlapping units leftward
        for i in range(len(gen_row) - 2, -1, -1):
            curr = gen_row[i]
            nxt  = gen_row[i + 1]
            max_cx = u_x[nxt] - nxt.width / 2 - H_GAP - curr.width / 2
            if u_x[curr] > max_cx:
                shift = u_x[curr] - max_cx
                for j in range(i + 1):
                    u_x[gen_row[j]] -= shift
        new_center = sum(u_x[u] for u in gen_row) / len(gen_row)
        center_shift = orig_center - new_center
        if abs(center_shift) > 1e-6:
            for u in gen_row:
                u_x[u] += center_shift

    # Write back into unit objects
    for u in units:
        u.x = u_x[u]
        u.y = u_y[u]

    return p2u


# ══════════════════════════════════════════════════════════════════
#  Main window
# ══════════════════════════════════════════════════════════════════

class TreeEditor(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Family Tree Editor")
        self.resize(1100, 700)

        self.people         = {}
        self.current_person = None
        self.compare_person = None
        self.node_items     = {}

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout()
        central_widget.setLayout(self.main_layout)

        self.title_label = QLabel("Family Tree Editor")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        self.main_layout.addWidget(self.title_label)

        # ── Top controls ──────────────────────────────────────────
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

        # ── Graph + info panel ────────────────────────────────────
        graph_layout = QHBoxLayout()
        self.scene = QGraphicsScene()
        self.view  = PanGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        graph_layout.addWidget(self.view, stretch=3)

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

        # ── Bottom buttons ────────────────────────────────────────
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

        self.update_ui_state()
        self.apply_settings()
        self.setup_auto_save()

    # ── Window events ─────────────────────────────────────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)
        window_size    = min(self.width(), self.height())
        settings       = options.OptionsMenu.get_settings()
        base_font_size = settings.get('font_size', 12)
        self.title_label.setFont(QFont("Arial", max(base_font_size + 6, int(window_size * 0.03)), QFont.Weight.Bold))

    def apply_settings(self):
        options.OptionsMenu.apply_theme_to_window(self)
        settings       = options.OptionsMenu.get_settings()
        base_font_size = settings.get('font_size', 12)
        self.title_label.setFont(QFont("Arial", base_font_size + 10, QFont.Weight.Bold))

    def setup_auto_save(self):
        settings = options.OptionsMenu.get_settings()
        if settings.get('auto_save', False):
            self.auto_save_timer = QTimer(self)
            self.auto_save_timer.timeout.connect(self.auto_save_tree)
            self.auto_save_timer.start(30000)
        else:
            if hasattr(self, 'auto_save_timer'):
                self.auto_save_timer.stop()

    def auto_save_tree(self):
        if self.people:
            try:
                self.serialize_json("family_tree.json")
                print("Auto-saved family tree")
            except Exception as e:
                print(f"Auto-save failed: {e}")

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    # ── UI state helpers ──────────────────────────────────────────
    def update_ui_state(self):
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
        selected_id = self.current_person.id if self.current_person else None
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
        sid = self.person_selector.currentData()
        if sid and sid in self.people:
            self.set_current_person(self.people[sid])

    def on_compare_person_changed(self):
        sid = self.compare_person_selector.currentData()
        self.compare_person = self.people.get(sid) if sid else None
        self.update_relationship_display()

    def update_relationship_display(self):
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

    def set_current_person(self, person):
        self.current_person = person
        for node in self.node_items.values():
            node.update_style(selected=(node.person is person))
        self.update_ui_state()

    def display_current_person(self):
        if not self.current_person:
            return
        self.name_label.setText(
            f"Name: {self.current_person.name} | DOB: {self.current_person.dob} | ID: {self.current_person.id[:8]}")
        parents  = ", ".join(p.name for p in self.current_person.parents) or "None"
        children = ", ".join(c.name for c in self.current_person.children) or "None"
        partner  = self.current_person.partner.name if self.current_person.partner else "None"
        self.relations_label.setText(f"Parents: {parents}\nChildren: {children}\nPartner: {partner}")

    # ── CRUD ──────────────────────────────────────────────────────
    def delete_current_person(self):
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
            self.current_person.last_name  = data["last_name"]
            self.current_person.name       = f"{data['first_name']} {data['last_name']}".strip()
            self.current_person.dob        = data["dob"]
            self.current_person.gender     = data["gender"]
            self.update_ui_state()

    def create_root_person(self):
        new_person = self.create_person_dialog("Root person")
        if new_person:
            self.people[new_person.id] = new_person
            self.set_current_person(new_person)
            self.update_ui_state()

    def create_person_dialog(self, title):
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

    def choose_existing_person(self, exclude=None):
        candidates = [p for p in self.people.values() if p is not exclude]
        if not candidates:
            QMessageBox.information(self, "No Existing Person", "No existing person available.")
            return None
        opts   = [f"{p.name} ({p.id[:8]})" for p in candidates]
        item, ok = QInputDialog.getItem(self, "Choose Person", "Select existing person:", opts, editable=False)
        if ok and item:
            for p in candidates:
                if item.startswith(p.name):
                    return p
        return None

    # ── Visibility (unchanged from original) ─────────────────────
    def get_visible_people(self):
        if not self.current_person:
            return set(self.people.values())

        blood_relatives = set()
        ancestors = set()
        queue = [self.current_person]
        while queue:
            curr = queue.pop(0)
            if curr not in ancestors:
                ancestors.add(curr)
                queue.extend(curr.parents)

        roots = list(ancestors) if ancestors else [self.current_person]
        queue = roots.copy()
        while queue:
            curr = queue.pop(0)
            if curr not in blood_relatives:
                blood_relatives.add(curr)
                queue.extend(curr.children)

        visible = set()
        for person in blood_relatives:
            visible.add(person)
            visible.update(person.parents)
            if person.partner:
                visible.add(person.partner)

        if self.current_person.partner:
            spouse = self.current_person.partner
            visible.add(spouse)
            visible.update(spouse.parents)
            for p in spouse.parents:
                visible.update(p.children)

        return visible

    # ── Persistence ───────────────────────────────────────────────
    def build_person_data(self, person):
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
            ET.SubElement(p_elem, "last_name").text  = person.last_name
            ET.SubElement(p_elem, "dob").text         = person.dob
            parents_elem = ET.SubElement(p_elem, "parents")
            for pid in [p.id for p in person.parents]:
                ET.SubElement(parents_elem, "parent").text = pid
            children_elem = ET.SubElement(p_elem, "children")
            for cid in [c.id for c in person.children]:
                ET.SubElement(children_elem, "child").text = cid
            ET.SubElement(p_elem, "partner").text = person.partner.id if person.partner else ""
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

    def load_from_dict(self, data):
        self.people.clear()
        self.current_person = None
        for p_data in data.get("people", []):
            p = Person(
                first_name=p_data.get("first_name"),
                last_name=p_data.get("last_name"),
                dob=p_data.get("dob"),
                person_id=p_data.get("id"),
                gender=p_data.get("gender"),
            )
            self.people[p.id] = p
        for p_data in data.get("people", []):
            p = self.people.get(p_data["id"])
            if not p: continue
            for pid in p_data.get("parents", []):
                par = self.people.get(pid)
                if par: p.add_parent(par)
            for cid in p_data.get("children", []):
                ch = self.people.get(cid)
                if ch: p.add_child(ch)
            partner_id = p_data.get("partner")
            if partner_id:
                partner = self.people.get(partner_id)
                if partner: p.set_partner(partner)
        if self.people:
            self.set_current_person(next(iter(self.people.values())))
        self.update_ui_state()

    def deserialize_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            self.load_from_dict(json.load(f))

    def deserialize_xml(self, path):
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
        settings       = options.OptionsMenu.get_settings()
        default_format = settings.get('export_format', 'JSON')
        if default_format == 'XML':
            default_name = "family_tree.xml"
            file_filter  = "XML Files (*.xml);;JSON Files (*.json)"
        else:
            default_name = "family_tree.json"
            file_filter  = "JSON Files (*.json);;XML Files (*.xml)"
        path, selected = QFileDialog.getSaveFileName(self, "Save Family Tree", default_name, file_filter)
        if not path: return
        try:
            if path.lower().endswith(".xml") or selected.startswith("XML"):
                self.serialize_xml(path)
            else:
                self.serialize_json(path)
            QMessageBox.information(self, "Save Successful", f"Saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save:\n{e}")

    def load_tree(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Family Tree", "", "JSON Files (*.json);;XML Files (*.xml)")
        if not path: return
        try:
            if path.lower().endswith(".xml"):
                self.deserialize_xml(path)
            else:
                self.deserialize_json(path)
            QMessageBox.information(self, "Load Successful", f"Loaded from {path}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load:\n{e}")

    def manage_relationship(self, relationship):
        if not self.current_person:
            return
        choice, ok = QInputDialog.getItem(
            self, "Relationship Action", "Choose action:",
            ["Create New Person", "Add Existing Person"], editable=False)
        if not ok: return

        target = None
        if choice == "Create New Person":
            target = self.create_person_dialog(f"Create {relationship.title()}")
            if target:
                self.people[target.id] = target
        elif choice == "Add Existing Person":
            target = self.choose_existing_person(exclude=self.current_person)
        if not target: return

        if relationship == "parent":
            self.current_person.add_parent(target)
            target.add_child(self.current_person)
            if len(self.current_person.parents) == 2:
                p1, p2 = list(self.current_person.parents)[:2]
                p1.set_partner(p2)
                p2.set_partner(p1)
        elif relationship == "child":
            self.current_person.add_child(target)
            target.add_parent(self.current_person)
            if self.current_person.partner:
                self.current_person.partner.add_child(target)
                target.add_parent(self.current_person.partner)
        elif relationship == "partner":
            self.current_person.set_partner(target)
            target.set_partner(self.current_person)

        self.set_current_person(self.current_person)

    # ══════════════════════════════════════════════════════════════
    #  FAMILY ECHO–STYLE GRAPH RENDERER
    # ══════════════════════════════════════════════════════════════
    def refresh_graph(self):
        self.scene.clear()
        self.node_items = {}

        if not self.people:
            self.scene.addText("Create or load a person to start your tree.")
            return

        visible = self.get_visible_people()
        if not visible:
            return

        focus = self.current_person if self.current_person in visible else next(iter(visible))

        # ── 1. Build units & assign generations ──────────────────
        units   = _build_units(visible, focus=focus)
        gen_map = _assign_generations(visible, focus)
        p2u     = _layout_units(units, gen_map, focus=focus)

        # ── 2. Place node items ───────────────────────────────────
        for unit in units:
            if len(unit.members) == 1:
                p    = unit.members[0]
                node = NodeItem(p, self.set_current_person)
                node.setPos(unit.x - NODE_W / 2, unit.y)
                self.scene.addItem(node)
                self.node_items[p.id] = node
            else:
                # Two partners: left card | gap | right card
                p1, p2 = unit.members[0], unit.members[1]
                n1 = NodeItem(p1, self.set_current_person)
                n2 = NodeItem(p2, self.set_current_person)
                # Left person
                x1 = unit.x - COUPLE_GAP / 2 - NODE_W
                x2 = unit.x + COUPLE_GAP / 2
                n1.setPos(x1, unit.y)
                n2.setPos(x2, unit.y)
                self.scene.addItem(n1)
                self.scene.addItem(n2)
                self.node_items[p1.id] = n1
                self.node_items[p2.id] = n2

        # ── 3. Draw connecting lines ──────────────────────────────
        self._draw_lines(units, visible, p2u)

        # ── 4. Highlight selected ─────────────────────────────────
        if self.current_person and self.current_person.id in self.node_items:
            self.node_items[self.current_person.id].update_style(True)

        bounds = self.scene.itemsBoundingRect().adjusted(-80, -80, 80, 80)
        self.scene.setSceneRect(bounds)
        if self.current_person and self.current_person.id in self.node_items:
            self.view.centerOn(self.node_items[self.current_person.id])

    def _line(self, x1, y1, x2, y2, pen):
        """Draw a single straight line segment (z=-1 so it sits behind cards)."""
        item = self.scene.addLine(x1, y1, x2, y2, pen)
        item.setZValue(-1)
        return item

    def _draw_lines(self, units, visible, p2u):
        """
        Family Echo orthogonal connector style:

        Partners
        ────────
          card1 ──── card2
                  |           (drop line from midpoint)
            ──────────        (horizontal crossbar at child-drop level)
            |    |    |
           ch1  ch2  ch3

        Single parent
        ─────────────
          card
           |
           ch
        """
        couple_pen  = QPen(COL_LINE_COUPLE, 1.8, Qt.PenStyle.SolidLine)
        child_pen   = QPen(COL_LINE_CHILD,  1.8, Qt.PenStyle.SolidLine)

        drawn_couple = set()
        # Map: frozenset(parent_ids) -> drop_x  (x of the vertical drop line)
        couple_drop_x = {}

        # ── Partner lines ─────────────────────────────────────────
        for unit in units:
            if len(unit.members) != 2:
                continue
            p1, p2 = unit.members
            key    = frozenset([p1.id, p2.id])
            if key in drawn_couple:
                continue
            drawn_couple.add(key)

            n1 = self.node_items.get(p1.id)
            n2 = self.node_items.get(p2.id)
            if not (n1 and n2):
                continue

            # Right edge of left card → left edge of right card  (horizontal bridge)
            r1  = n1.sceneBoundingRect()
            r2  = n2.sceneBoundingRect()
            mid_y = (r1.center().y() + r2.center().y()) / 2

            # Horizontal line connecting the two partner cards at mid-height
            self._line(r1.right(), mid_y, r2.left(), mid_y, couple_pen)

            # Drop point = midpoint of the bridge
            drop_x = (r1.right() + r2.left()) / 2
            couple_drop_x[key] = drop_x

        # ── Child lines ───────────────────────────────────────────
        # Group children by their parent-unit
        for unit in units:
            # Collect visible children of this unit
            children_vis = []
            for m in unit.members:
                for ch in m.children:
                    if ch.id in self.node_items:
                        children_vis.append(ch)

            # Deduplicate while preserving order
            seen = set()
            ch_dedup = []
            for ch in children_vis:
                if ch.id not in seen:
                    seen.add(ch.id)
                    ch_dedup.append(ch)
            children_vis = ch_dedup

            if not children_vis:
                continue

            # Determine the "origin" x,y of lines coming down from this unit
            if len(unit.members) == 2:
                p1, p2 = unit.members
                key    = frozenset([p1.id, p2.id])
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
                r        = self.node_items[p.id].sceneBoundingRect()
                origin_x = r.center().x()
                origin_y = r.bottom()

            if len(children_vis) == 1:
                # Single child: straight vertical line
                ch   = children_vis[0]
                ch_r = self.node_items[ch.id].sceneBoundingRect()
                ch_x = ch_r.center().x()
                ch_y = ch_r.top()

                # Vertical from parent bottom
                mid_y = (origin_y + ch_y) / 2
                self._line(origin_x, origin_y, origin_x, mid_y, child_pen)
                # Horizontal jog if child is offset
                self._line(origin_x, mid_y, ch_x, mid_y, child_pen)
                # Vertical to child top
                self._line(ch_x, mid_y, ch_x, ch_y, child_pen)
            else:
                # Multiple children: vertical drop → horizontal crossbar → verticals up to each child
                child_xs = []
                for ch in children_vis:
                    ch_r = self.node_items[ch.id].sceneBoundingRect()
                    child_xs.append(ch_r.center().x())

                crossbar_y = origin_y + GEN_H_GAP * 0.45

                # Vertical drop from parent to crossbar
                self._line(origin_x, origin_y, origin_x, crossbar_y, child_pen)

                # Horizontal crossbar spanning all children
                bar_left  = min(child_xs)
                bar_right = max(child_xs)
                self._line(bar_left, crossbar_y, bar_right, crossbar_y, child_pen)

                # Vertical stubs from crossbar down to each child's top
                for ch, cx in zip(children_vis, child_xs):
                    ch_r = self.node_items[ch.id].sceneBoundingRect()
                    self._line(cx, crossbar_y, cx, ch_r.top(), child_pen)

    # ── Legacy helpers kept for completeness ─────────────────────
    def find_root_person(self, visible_people):
        candidates = [p for p in visible_people if not any(par in visible_people for par in p.parents)]
        return candidates[0] if candidates else next(iter(visible_people))

    def compute_levels(self, root, visible_people):
        levels  = {}
        visited = set()
        queue   = [(root, 0)]
        while queue:
            person, level = queue.pop(0)
            if person.id in visited: continue
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