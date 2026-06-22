"""
relation.py

Job:
----
This module calculates the family relationship between any two individuals in the tree.
It determines both the path of people connecting them (e.g. A -> parent -> B -> partner -> C)
and translates that path into a human-friendly gender-specific English title (e.g. "Wife",
"Uncle", "Second Cousin once removed", or "Mother-in-law").

How it works:
-------------
1. It uses a Breadth-First Search (BFS) pathfinding algorithm on the family network.
   Starting from Person A, it traverses parent, child, and partner links until it finds Person B.
   It logs the path of people traversed and whether the relationship includes a marriage/partner link
   (which makes it an "in-law" relationship).
2. It analyzes the generational step changes (how many steps up to ancestors vs how many steps
   down to descendants) to map the relationship structure.
3. It converts the step counts and the gender of the target person into a relationship name.
"""

from collections import deque
from typing import Optional, Tuple, List
from person import Person


def find_relationship_bfs(person1: Person, person2: Person) -> Optional[Tuple[List[Person], bool]]:
    """
    Job:
    ----
    Finds the shortest path of people connecting person1 to person2.

    How it does it:
    --------------
    - Employs Breadth-First Search (BFS) queue.
    - Queue stores tuples of: (current_person, path_list, is_in_law_flag).
    - It visits adjacent connections: parents, children, and partner.
    - If it traverses a partner link, the 'is_in_law' flag is set to True.
    - Returns a tuple of (path, is_in_law) if a path is found, otherwise returns None.
    """
    if person1 is person2:
        return ([person1], False)
    
    queue = deque() 
    # Add starting person. Path list starts with just person1, in-law flag starts as False.
    queue.append((person1, [person1], False)) 

    visited = set() # Avoid infinite loops by tracking visited individuals
    visited.add(person1)

    while queue:
        current, path, in_law = queue.popleft() 

        # If we reached the target person, return the path and in-law flag.
        if current is person2:
            return (path, in_law)

        # 1. Check parents (generation step up)
        for parent in current.parents:
            if parent not in visited:
                visited.add(parent)
                queue.append((parent, path + [parent], in_law))

        # 2. Check children (generation step down)
        for child in current.children:
            if child not in visited:
                visited.add(child)
                queue.append((child, path + [child], in_law))

        # 3. Check partner (marriage transition)
        if current.partner and current.partner not in visited:
            visited.add(current.partner)
            # Crossing a partner link marks this path and all downstream steps as in-law.
            queue.append((current.partner, path + [current.partner], True))
    
    return None # Returns None if there is no connection between the two people


def get_relationship_title(result_tuple: Optional[Tuple[List[Person], bool]]) -> str:
    """
    Job:
    ----
    Converts a BFS path search result into a descriptive English string.

    How it does it:
    --------------
    - Decodes the path to count generational shifts up (parents) and down (children).
    - Checks the gender of the target person to choose the right terms (e.g. Father vs Mother).
    - Evaluates structural rules:
      - up=1, down=0 -> Parent
      - up=2, down=0 -> Grandparent
      - up=0, down=1 -> Child
      - up=1, down=1 -> Sibling
      - up=2, down=1 -> Aunt/Uncle
      - up=1, down=2 -> Niece/Nephew
      - up>=2, down>=2 -> Cousins (uses min(up, down)-1 for degree, and abs(up-down) for times removed).
    - If the in-law flag is true, it appends "-in-law" to the computed title.
    """
    if not result_tuple:
        return "No relationship found"
        
    path, is_in_law = result_tuple
    
    if len(path) == 1:
        return "Self"
        
    target_person = path[-1]
    
    # Safely get gender of the target person, defaulting to neutral 'n' if not set
    raw_gender = getattr(target_person, 'gender', None)
    gender_str = str(raw_gender).lower() if raw_gender else 'n'
    
    is_male = gender_str.startswith('m')
    is_female = gender_str.startswith('f')

    # Handle direct marriage partners (spouse)
    if len(path) == 2 and is_in_law:
        if is_male: 
            return "Husband"
        if is_female: 
            return "Wife"
        return "Partner/Spouse"

    # Count the directional generation steps along the path
    up_steps = 0
    down_steps = 0

    for i in range(len(path) - 1):
        current_person = path[i]
        next_person = path[i+1]

        if next_person in current_person.parents:
            up_steps += 1
        elif next_person in current_person.children:
            down_steps += 1

    base_title = ""
    
    # 1. Direct Ancestors (going only up)
    if up_steps > 0 and down_steps == 0:
        if is_male: 
            noun = "Father"
        elif is_female: 
            noun = "Mother"
        else: 
            noun = "Parent"
        
        if up_steps == 1: 
            base_title = noun
        elif up_steps == 2: 
            base_title = f"Grand{noun.lower()}"
        else: 
            base_title = ("Great-" * (up_steps - 2)) + f"Grand{noun.lower()}"
        
    # 2. Direct Descendants (going only down)
    elif down_steps > 0 and up_steps == 0:
        if is_male: 
            noun = "Son"
        elif is_female: 
            noun = "Daughter"
        else: 
            noun = "Child"
        
        if down_steps == 1: 
            base_title = noun
        elif down_steps == 2: 
            base_title = f"Grand{noun.lower()}"
        else: 
            base_title = ("Great-" * (down_steps - 2)) + f"Grand{noun.lower()}"
        
    # 3. Siblings (up 1 step to parent, down 1 step to their child)
    elif up_steps == 1 and down_steps == 1:
        if is_male: 
            base_title = "Brother"
        elif is_female: 
            base_title = "Sister"
        else: 
            base_title = "Sibling"
        
    # 4. Aunts and Uncles (up 2+ steps to grandparents, down 1 step to parent's sibling)
    elif up_steps > 1 and down_steps == 1:
        if is_male: 
            noun = "Uncle"
        elif is_female: 
            noun = "Aunt"
        else: 
            noun = "Aunt/Uncle"
        
        if up_steps == 2: 
            base_title = noun
        else: 
            base_title = ("Great-" * (up_steps - 2)) + noun
        
    # 5. Nieces and Nephews (up 1 step to parent, down 2+ steps to sibling's child)
    elif up_steps == 1 and down_steps > 1:
        if is_male: 
            noun = "Nephew"
        elif is_female: 
            noun = "Niece"
        else: 
            noun = "Niece/Nephew"
        
        if down_steps == 2: 
            base_title = noun
        else: 
            base_title = ("Great-" * (down_steps - 2)) + noun
        
    # 6. Cousins (going up to grandparents/common ancestor and down to cousin)
    elif up_steps >= 2 and down_steps >= 2:
        # Degree (1st, 2nd, 3rd cousin) is determined by the minimum common ancestor step level
        degree = min(up_steps, down_steps) - 1
        # Times removed (1x, 2x removed) is the generational difference between the two people
        removed = abs(up_steps - down_steps)
        
        degree_str = _ordinal(degree) 
        
        if removed == 0:
            base_title = f"{degree_str} Cousin"
        else:
            base_title = f"{degree_str} Cousin {removed}x removed"

    # Add the "-in-law" suffix if path crossed a marriage link
    if is_in_law and base_title:
        return f"{base_title}-in-law"
        
    return base_title if base_title else "Distant relative"


def _ordinal(n: int) -> str:
    """
    Job:
    ----
    Converts an integer number into its English ordinal string (e.g. 1 -> First, 2 -> Second).
    Used to describe cousin degrees.
    """
    base = n
    n = n % 10
    if n == 1 and base%100 != 11:
        return f"{base}st"
    elif n == 2 and base%100 != 12:
        return f"{base}nd"
    elif n == 3 and base%100 != 13:
        return f"{base}rd"
    else:
        return f"{base}th"
