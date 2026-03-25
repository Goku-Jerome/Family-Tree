"""Functions to find relationship between two people"""
from collections import deque
from typing import Optional, Tuple, List
from person import Person



def find_relationship_bfs(person1: Person, person2: Person):
    """Find the relationship between any two individuals."""

    if person1 is person2:
        return "Same person"
    
    queue = deque() #create a queue for breadth-first search
    queue.append((person1, [person1], False)) #add person 1 to the queue, the path so far is just person 1 and the in-law flag is false

    visited = set() #keep track of visited people to avoid cycles
    visited.add(person1)

    while queue:
        current, path, in_law = queue.popleft() #get the next person and the path to them

        if current is person2: #if we found person 2, return the relationship
            return (path, in_law)

        # Explore parents
        for parent in current.parents:
            if parent not in visited:
                visited.add(parent)
                queue.append((parent, path + [parent], in_law))

        # Explore children
        for child in current.children:
            if child not in visited:
                visited.add(child)
                queue.append((child, path + [child], in_law))

        # Explore partner
        if current.partner and current.partner not in visited:
            visited.add(current.partner)
            queue.append((current.partner, path + [current.partner], True)) #partner is an in-law relationship
    
    return None #if person 2 is not found, return None


def get_relationship_title(result_tuple: Optional[Tuple[List[Person], bool]]) -> str:
    """Converts a BFS result tuple into a gender-specific English relationship string."""
    
    if not result_tuple:
        return "No relationship found"
        
    path, is_in_law = result_tuple
    
    if len(path) == 1:
        return "Self"
        
    target_person = path[-1]
    
    # SAFELY HANDLE GENDER: Fallback to 'n' if missing, None, or empty
    raw_gender = getattr(target_person, 'gender', None)
    gender_str = str(raw_gender).lower() if raw_gender else 'n'
    
    is_male = gender_str.startswith('m')
    is_female = gender_str.startswith('f')

    # Handle direct partners
    if len(path) == 2 and is_in_law:
        if is_male: return "Husband"
        if is_female: return "Wife"
        return "Partner/Spouse"

    # Count the generational steps
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
    
    # Direct Ancestors
    if up_steps > 0 and down_steps == 0:
        if is_male: noun = "Father"
        elif is_female: noun = "Mother"
        else: noun = "Parent"
        
        if up_steps == 1: base_title = noun
        elif up_steps == 2: base_title = f"Grand{noun.lower()}"
        else: base_title = ("Great-" * (up_steps - 2)) + f"Grand{noun.lower()}"
        
    # Direct Descendants
    elif down_steps > 0 and up_steps == 0:
        if is_male: noun = "Son"
        elif is_female: noun = "Daughter"
        else: noun = "Child"
        
        if down_steps == 1: base_title = noun
        elif down_steps == 2: base_title = f"Grand{noun.lower()}"
        else: base_title = ("Great-" * (down_steps - 2)) + f"Grand{noun.lower()}"
        
    # Siblings
    elif up_steps == 1 and down_steps == 1:
        if is_male: base_title = "Brother"
        elif is_female: base_title = "Sister"
        else: base_title = "Sibling"
        
    # Aunts and Uncles
    elif up_steps > 1 and down_steps == 1:
        if is_male: noun = "Uncle"
        elif is_female: noun = "Aunt"
        else: noun = "Aunt/Uncle"
        
        if up_steps == 2: base_title = noun
        else: base_title = ("Great-" * (up_steps - 2)) + noun
        
    # Nieces and Nephews
    elif up_steps == 1 and down_steps > 1:
        if is_male: noun = "Nephew"
        elif is_female: noun = "Niece"
        else: noun = "Niece/Nephew"
        
        if down_steps == 2: base_title = noun
        else: base_title = ("Great-" * (down_steps - 2)) + noun
        
    # Cousins 
    elif up_steps >= 2 and down_steps >= 2:
        degree = min(up_steps, down_steps) - 1
        removed = abs(up_steps - down_steps)
        
        # Assuming your _ordinal() function is still in scope
        degree_str = _ordinal(degree) 
        
        if removed == 0:
            base_title = f"{degree_str} Cousin"
        else:
            base_title = f"{degree_str} Cousin {removed}x removed"

    # Apply In-Law Modifier
    if is_in_law:
        return f"{base_title}-in-law"
        
    return base_title




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
