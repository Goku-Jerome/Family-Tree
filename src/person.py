import uuid

# person.py
# This module is the data model for one person in the family tree.
# It holds name, birth date, and family relationships.

class Person:
    """Simple data container representing one person in the tree."""

    def __init__(self, first_name="Unnamed", last_name="Unnamed", dob=None, person_id=None):
        # Unique ID is either given or generated.
        self.id = person_id or str(uuid.uuid4())

        # Keep inputs clean; if empty names are provided, use "Unnamed".
        self.first_name = first_name.strip() if first_name and first_name.strip() else "Unnamed"
        self.last_name = last_name.strip() if last_name and last_name.strip() else "Unnamed"
        self.name = f"{self.first_name} {self.last_name}".strip()

        # Again, fallback default for date of birth.
        self.dob = dob.strip() if dob and dob.strip() else "Unknown"

        # Relationships start empty; will be connected by the editor.
        self.parents = []
        self.children = []
        self.partner = None

    def __str__(self):
        # Human-friendly text when this object is printed.
        return self.name
    

    def add_parent(self, parent):
        """Make another Person a parent of this one."""
        if parent is self:
            return
        if parent not in self.parents:
            self.parents.append(parent)
        if self not in parent.children:
            parent.children.append(self)

    def add_child(self, child):
        """Add a child relationship in both directions."""
        if child is self:
            return
        if child not in self.children:
            self.children.append(child)
        if self not in child.parents:
            child.parents.append(self)

    def set_partner(self, partner):
        """Set the partner/spouse relationship between two people."""
        if partner is self:
            return

        # If the current person had another partner before, clear that old link.
        if self.partner and self.partner is not partner:
            self.partner.partner = None

        # If the new partner had a different partner, clear that too.
        if partner.partner and partner.partner is not self:
            partner.partner.partner = None

        self.partner = partner
        partner.partner = self

    def describe(self):
        """Return a readable summary string for this person."""
        return (
            f"{self.name} (DOB: {self.dob}, ID: {self.id}) "
            f"Parents: {len(self.parents)}, Children: {len(self.children)}, "
            f"Partner: {self.partner.name if self.partner else 'None'}"
        )
