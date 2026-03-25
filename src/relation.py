"""Functions to find relationship between two people"""
from collections import deque
from typing import Optional, Tuple, List
from person import Person


def detect_blood_relation(person1: Person, person2: Person) -> bool:
    """
    Detect if two people have a blood relation (genetic connection).
    Only follows parent-child links, not partner links.
    
    Args:
        person1: First person
        person2: Second person
    
    Returns:
        True if there is a blood relation between them, False otherwise
    """
    if person1 is person2:
        return True
    
    # BFS using only parent-child connections
    visited = {person1}
    queue = deque([person1])
    
    while queue:
        current = queue.popleft()
        
        # Check parents
        for parent in current.parents:
            if parent is person2:
                return True
            if parent not in visited:
                visited.add(parent)
                queue.append(parent)
        
        # Check children
        for child in current.children:
            if child is person2:
                return True
            if child not in visited:
                visited.add(child)
                queue.append(child)
    
    return False


def _find_path_bfs(person1: Person, person2: Person, blood_only: bool = False) -> Optional[List[Tuple[Person, str]]]:
    """
    Find the shortest path between two people using BFS.
    Returns a list of (person, relation_type) tuples representing the path.
    
    Args:
        person1: Starting person
        person2: Target person
        blood_only: If True, only follow parent-child links; if False, include partner links
    
    Returns:
        List of (person, direction) tuples showing the path, or None if no path exists
    """
    if person1 is person2:
        return [(person1, "self")]
    
    visited = {person1}
    queue = deque([(person1, [(person1, "self")])])
    
    while queue:
        current, path = queue.popleft()
        
        # Get all connections from current person
        connections = []
        
        # Parent connections
        for parent in current.parents:
            connections.append((parent, "parent"))
        
        # Child connections
        for child in current.children:
            connections.append((child, "child"))
        
        # Partner connection (only if not blood_only)
        if not blood_only and current.partner:
            connections.append((current.partner, "partner"))
        
        for next_person, relation_type in connections:
            if next_person is person2:
                return path + [(next_person, relation_type)]
            
            if next_person not in visited:
                visited.add(next_person)
                queue.append((next_person, path + [(next_person, relation_type)]))
    
    return None


def _path_to_relationship(path: List[Tuple[Person, str]]) -> str:
    """
    Convert a path through the family tree to a human-readable relationship.
    
    Args:
        path: List of (person, direction) tuples from BFS
    
    Returns:
        A string describing the relationship
    """
    if len(path) < 2:
        return "Self"
    
    # Analyze the path structure
    directions = [direction for _, direction in path[1:]]
    
    # Direct relationships
    if len(directions) == 1:
        direction = directions[0]
        if direction == "parent":
            return "Parent"
        elif direction == "child":
            return "Child"
        elif direction == "partner":
            return "Partner"
    
    # Siblings (share parents)
    if len(directions) == 2 and directions == ["parent", "child"]:
        return "Sibling"
    
    # Grandparent/Grandchild
    if directions.count("parent") == 2 and directions.count("child") == 0 and "partner" not in directions:
        return "Grandparent"
    if directions.count("child") == 2 and directions.count("parent") == 0 and "partner" not in directions:
        return "Grandchild"
    
    # Great-grandparent/Great-grandchild
    if directions.count("parent") == 3 and directions.count("child") == 0 and "partner" not in directions:
        return "Great-Grandparent"
    if directions.count("child") == 3 and directions.count("parent") == 0 and "partner" not in directions:
        return "Great-Grandchild"
    
    # Aunt/Uncle (sibling of parent)
    if (len(directions) == 3 and 
        directions[0:2] == ["parent", "parent"] and 
        directions[2] == "child"):
        return "Aunt/Uncle"
    
    # Niece/Nephew (child of sibling)
    if (len(directions) == 3 and 
        directions[0:2] == ["parent", "child"] and 
        directions[2] == "child"):
        return "Niece/Nephew"
    
    # Cousin (parent's sibling's child)
    if (len(directions) == 4 and 
        directions[0:2] == ["parent", "parent"] and
        directions[2:4] == ["child", "child"] and
        "partner" not in directions):
        return "First Cousin"
    
    # First Cousin Once Removed
    if (len(directions) == 5 and
        directions == ["parent", "parent", "child", "child", "child"] and
        "partner" not in directions):
        return "First Cousin Once Removed (Descendent)"
    
    if (len(directions) == 5 and
        directions == ["parent", "parent", "parent", "child", "child"] and
        "partner" not in directions):
        return "First Cousin Once Removed (Ancestor)"
    
    # In-law relationships (involves partner link)
    if "partner" in directions:
        partner_idx = directions.index("partner")
        before_partner = directions[:partner_idx]
        after_partner = directions[partner_idx + 1:]
        
        # If partner appears early in path
        if len(before_partner) == 0:
            # Direct partner
            if len(after_partner) == 0:
                return "Partner"
            # Partner's relatives
            elif len(after_partner) == 1 and after_partner[0] == "parent":
                return "Parent-in-law"
            elif len(after_partner) == 1 and after_partner[0] == "child":
                return "Child-in-law"
            elif after_partner == ["parent", "parent"]:
                return "Grandparent-in-law"
            elif after_partner == ["parent", "child"]:
                return "Sibling-in-law"
            else:
                return f"Partner's {_path_to_relationship([(None, d) for d in after_partner])}"
        
        # If someone's relative married to your relative (spouse's sibling of your relative)
        elif len(before_partner) == 2 and before_partner == ["parent", "child"] and len(after_partner) >= 1:
            # Your sibling's partner's relative
            return f"Sibling-in-law's {_path_to_relationship([(None, d) for d in after_partner])}"
        
        # Standard parent -> uncle -> uncle's wife scenario (Jerome -> uncle -> uncle's wife)
        elif len(before_partner) == 2 and before_partner == ["parent", "parent"] and len(after_partner) >= 1:
            # Parent's sibling's partner
            if after_partner == []:
                return "Aunt/Uncle-in-law"
            else:
                return f"Aunt/Uncle-in-law's {_path_to_relationship([(None, d) for d in after_partner])}"
        
        else:
            return f"In-law relation"
    
    # Fallback for complex paths
    up_count = directions.count("parent")
    down_count = directions.count("child")
    
    if up_count > 0 and down_count == 0:
        return f"{up_count} generations up"
    elif down_count > 0 and up_count == 0:
        return f"{down_count} generations down"
    else:
        # Path that goes up then down = cousin-like relationship
        if up_count > 0 and down_count > 0:
            common_ancestor_distance = max(up_count - 1, 0)
            cousin_degree = min(up_count, down_count) - 1
            removed = abs(up_count - down_count)
            
            if cousin_degree < 0:
                return "Aunt/Uncle or Niece/Nephew"
            elif cousin_degree == 0:
                if removed == 0:
                    return "Sibling"
                else:
                    return f"Sibling (but actually first cousin once removed)"
            else:
                if removed == 0:
                    return f"{_ordinal(cousin_degree)} Cousin"
                else:
                    return f"{_ordinal(cousin_degree)} Cousin {removed}x Removed"
    
    return "Distant Relative"


def _ordinal(n: int) -> str:
    """Convert a number to its ordinal representation."""
    if n == 1:
        return "First"
    elif n == 2:
        return "Second"
    elif n == 3:
        return "Third"
    elif n == 4:
        return "Fourth"
    elif n == 5:
        return "Fifth"
    else:
        return f"{n}th"


def find_relationship(person1: Person, person2: Person) -> Optional[str]:
    """
    Find the closest/most direct relationship between two people.
    Considers both blood relations and relations through marriage.
    
    Args:
        person1: First person
        person2: Second person
    
    Returns:
        A string describing the relationship, or None if no relation exists
    """
    if person1 is person2:
        return "Self"
    
    # Try to find path including marriage links
    path = _find_path_bfs(person1, person2, blood_only=False)
    
    if path is None:
        return None
    
    return _path_to_relationship(path)


def find_blood_relationship(person1: Person, person2: Person) -> Optional[str]:
    """
    Find the closest blood relation between two people.
    Only considers genetic connections (parents and children).
    
    Args:
        person1: First person
        person2: Second person
    
    Returns:
        A string describing the blood relationship, or None if no blood relation exists
    """
    if person1 is person2:
        return "Self"
    
    # Try to find path using only blood links
    path = _find_path_bfs(person1, person2, blood_only=True)
    
    if path is None:
        return None
    
    return _path_to_relationship(path)
