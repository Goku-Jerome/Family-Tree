import uuid

class Person:
    def __init__(self, first_name, last_name, dob=None, person_id=None):
        self.id = person_id or str(uuid.uuid4())
        self.first_name = first_name.strip() if first_name and first_name.strip() else "Unnamed"
        self.last_name = last_name.strip() if last_name and last_name.strip() else "Unnamed"
        self.name = f"{self.first_name} {self.last_name}".strip()
        self.dob = dob.strip() if dob and dob.strip() else "Unknown"
        self.parents = []
        self.children = []
        self.partner = None

    def __str__(self):
        return self.name

    def add_parent(self, parent):
        if parent is self:
            return
        if parent not in self.parents:
            self.parents.append(parent)
        if self not in parent.children:
            parent.children.append(self)

    def add_child(self, child):
        if child is self:
            return
        if child not in self.children:
            self.children.append(child)
        if self not in child.parents:
            child.parents.append(self)

    def set_partner(self, partner):
        if partner is self:
            return
        # unpair existing partners
        if self.partner and self.partner is not partner:
            self.partner.partner = None
        if partner.partner and partner.partner is not self:
            partner.partner.partner = None
        self.partner = partner
        partner.partner = self

    def describe(self):
        return (
            f"{self.name} (DOB: {self.dob}, ID: {self.id}) "
            f"Parents: {len(self.parents)}, Children: {len(self.children)}, "
            f"Partner: {self.partner.name if self.partner else 'None'}"
        )
