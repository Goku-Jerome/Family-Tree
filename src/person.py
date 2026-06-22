import uuid

# person.py
#
# Job:
# ----
# This module defines the Person class, which acts as the core data representation
# for a single individual in the family tree. It holds their personal details
# (name, gender, date of birth) and tracks their links to other people (parents,
# partner, and children).
#
# How it works:
# -------------
# The Person object stores connections to other Person objects in list and reference variables:
# - self.parents (a list of other Person objects representing the parents)
# - self.children (a list representing children)
# - self.partner (a single reference to their spouse/partner)
# When relationships are established (e.g. adding a child), the class updates BOTH
# individuals involved (e.g. adding the parent reference to the child, and the child reference to the parent).

class Person:
    """
    A representation of a single individual in the family tree.
    Stores personal identifiers, biographical details, and relationship pointers.
    """

    def __init__(self, first_name="Unnamed", last_name="Unnamed", dob=None, person_id=None, gender=None):
        """
        Job:
        ----
        Initializes a Person instance, assigning a unique identifier (UUID) and defaults
        if names or dates are left blank.

        Parameters:
        -----------
        - first_name (str): The person's given name. Defaults to "Unnamed".
        - last_name (str): The person's family name. Defaults to "Unnamed".
        - dob (str): Date of birth (expected format: YYYY-MM-DD). Defaults to "Unknown".
        - person_id (str): Existing unique ID (useful when loading from file). Generates a random UUID if None.
        - gender (str): Gender of the person ("Male", "Female", or other description).
        """
        # Assign a unique, machine-readable string ID to guarantee we can tell people apart
        # even if they have the exact same name and date of birth.
        self.id = person_id or str(uuid.uuid4())

        # Clean whitespace and enforce defaults to avoid empty strings in names.
        self.first_name = first_name.strip() if first_name and first_name.strip() else "Unnamed"
        self.last_name = last_name.strip() if last_name and last_name.strip() else "Unnamed"
        self.name = f"{self.first_name} {self.last_name}".strip()

        # Set birthdate, defaulting to "Unknown" if not provided.
        self.dob = dob.strip() if dob and dob.strip() else "Unknown"

        # Relationships: pointers to other Person instances.
        # These are modified dynamically using the helper methods below.
        self.parents = []    # List of Person instances (up to 2 in normal rendering)
        self.children = []   # List of Person instances (representing descendants)
        self.partner = None  # Single reference to a Person instance (spouse/partner)
        self.gender = gender

    def __str__(self):
        """
        Job:
        ----
        Returns a simple, readable string representation (usually just their name)
        whenever this object is printed or cast to a string.
        """
        return self.name
    
    def delete(self):
        """
        Job:
        ----
        Prepares this person object for deletion by severing all active relationship links.

        How it does it:
        --------------
        Iterates through parents, children, and partners, and removes self from their corresponding lists/pointers
        so we do not leave trailing references (dangling pointers) in the family database.
        """
        # Remove this person from all of their parents' children lists
        for parent in self.parents:
            if self in parent.children:
                parent.children.remove(self)

        # Remove this person from all of their children's parents lists
        for child in self.children:
            if self in child.parents:
                child.parents.remove(self)

        # Clear the partner link: tell the partner they are single, then clear self's link
        if self.partner:
            self.partner.partner = None
            self.partner = None

    def add_parent(self, parent):
        """
        Job:
        ----
        Establishes a parent-child relationship.

        How it does it:
        --------------
        Adds the parent to this person's parents list, and automatically adds this person
        to the parent's children list. Prevents self-linking and duplicates.
        """
        if parent is self:
            return
        if parent not in self.parents:
            self.parents.append(parent)
        if self not in parent.children:
            parent.children.append(self)

    def add_child(self, child):
        """
        Job:
        ----
        Establishes a child-parent relationship.

        How it does it:
        --------------
        Adds the child to this person's children list, and automatically adds this person
        to the child's parents list. Prevents self-linking and duplicates.
        """
        if child is self:
            return
        if child not in self.children:
            self.children.append(child)
        if self not in child.parents:
            child.parents.append(self)

    def set_partner(self, partner):
        """
        Job:
        ----
        Establishes a partner/spouse relationship.

        How it does it:
        --------------
        1. If this person already had a partner, it clears that old partner's link (divorce).
        2. If the new partner already had a partner, it clears their old partner's link.
        3. Updates the partner variable on both self and the new partner to point to each other.
        """
        if partner is self:
            return

        # Sever old connection for self if it exists
        if self.partner and self.partner is not partner:
            self.partner.partner = None

        # Sever old connection for the new partner if it exists
        if partner.partner and partner.partner is not self:
            partner.partner.partner = None

        # Link self and new partner
        self.partner = partner
        partner.partner = self

    def describe(self):
        """
        Job:
        ----
        Returns a detailed summary text containing the person's biographical details
        and counts of their parents, children, and spouse name. Useful for debugging or consoles.
        """
        return (
            f"{self.name} (DOB: {self.dob}, ID: {self.id}) "
            f"Parents: {len(self.parents)}, Children: {len(self.children)}, "
            f"Partner: {self.partner.name if self.partner else 'None'}"
        )
