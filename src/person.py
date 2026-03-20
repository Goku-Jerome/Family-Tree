import uuid

class Person:
    def __init__(self, name, person_id=None):
        self.id = person_id or str(uuid.uuid4())
        self.name = name.strip() if name and name.strip() else "Unnamed"
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
        return f"{self.name} (Parents: {len(self.parents)}, Children: {len(self.children)}, Partner: {self.partner.name if self.partner else 'None'})"
