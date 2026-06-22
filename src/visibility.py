import collections
from person import Person

def calculate_visible_people(focus_person: Person, all_people: dict, max_visible: int = 2000, expanded_branches: dict = None) -> set[Person]:
    """
    Job:
    ----
    This function determines which family members should be visible in the graphical editor
    canvas at any given time. It implements a priority-based visibility culling system to
    ensure the diagram remains readable and doesn't get cluttered, especially in large trees.

    How it works:
    -------------
    1. Starting from the selected 'focus_person', the algorithm performs a relationship-based 
       traversal to assign a 'priority level' (from 1 to 5) to other people in the database.
       - Tier 5: The focus person themselves (highest priority).
       - Tier 4: Direct ancestors (parents, grandparents) and descendants (children, grandchildren)
                 extending infinitely up and down the bloodline.
       - Tier 3: Partners of bloodline members, siblings of the focus person, partners of siblings,
                 and aunts/uncles plus first cousins.
       - Tier 2: Nieces/nephews, partners of nieces/nephews, partners of cousins, second cousins,
                 and immediate in-laws (parents of the focus person's partner).
       - Tier 1: Distant connections, such as the partner's siblings, grand-nieces/nephews, and
                 partners of second cousins.
    2. If the total number of reached candidates is less than or equal to 'max_visible',
       everyone is shown.
       If it exceeds 'max_visible', the system progressively cully (drops) the lowest priority
       tiers one by one (Tier 1, then Tier 2, then Tier 3) until the count is within the limit.
       Tiers 4 and 5 (direct bloodline ancestors and descendants) are never culled.
    
    Parameters:
    -----------
    - focus_person (Person): The person currently selected in the editor who acts as the center
                             of the visibility view.
    - all_people (dict[str, Person]): A dictionary mapping unique person IDs to Person objects,
                                     representing all individuals in the database.
    - max_visible (int): The soft limit on how many cards are allowed to be drawn at once.

    Returns:
    --------
    - set[Person]: A set of Person objects that should be drawn in the family tree graph.
    """
    # If no focus person is selected, default to showing everyone in the database.
    if not focus_person:
        return set(all_people.values())

    priority = {}                          # Maps Person -> priority tier (int)
    _people_ids = set(all_people.keys())   # Set of valid IDs for O(1) existence checks

    # Helper function to check if a person object exists in the active database.
    def _known(p):  
        return p.id in _people_ids

    # Helper function to assign priority. If a person is reached via multiple paths,
    # they keep the highest priority level assigned.
    def _set(p, pri):
        if p not in priority or priority[p] < pri:
            priority[p] = pri

    # ── Tiers 5 & 4: Focus person, direct ancestors, and direct descendants ──
    _set(focus_person, 5)

    if expanded_branches is None:
        expanded_branches = {}

    def is_expanded(p: Person) -> bool:
        """Determines if we should trace upwards from this person."""
        # If explicitly set in the UI, ALWAYS respect user choice
        if p.partner and _known(p.partner):
            key = frozenset([p.id, p.partner.id])
            if key in expanded_branches:
                return expanded_branches[key] == p.id
                
        # Default rules if no explicit choice was made:
        # 1. Focus person and their immediate parents are ALWAYS expanded
        if p is focus_person or p in focus_person.parents:
            return True
            
        # 2. If they have no partner, they are naturally expanded (single parent line)
        if not p.partner or not _known(p.partner):
            return True
            
        # 3. Default to the male (paternal line)
        pg = str(p.gender).lower() if p.gender else ""
        partner_g = str(p.partner.gender).lower() if p.partner.gender else ""
        if pg.startswith("m") and not partner_g.startswith("m"):
            return True
        elif not pg.startswith("m") and partner_g.startswith("m"):
            return False
            
        # 4. Fallback to ID sorting
        return p.id < p.partner.id

    # Walk upwards to collect all ancestors (parents, grandparents, great-grandparents, etc.)
    anc_q = collections.deque([focus_person])
    anc_seen = {focus_person}
    while anc_q:
        p = anc_q.popleft()
        
        # STOP CONDITION: If person is not the expanded spouse, stop tracing their parents
        if not is_expanded(p):
            continue
            
        for par in p.parents:
            if _known(par) and par not in anc_seen:
                anc_seen.add(par)
                _set(par, 4)
                anc_q.append(par)

    # Walk downwards to collect all descendants (children, grandchildren, great-grandchildren, etc.)
    desc_q = collections.deque([focus_person])
    desc_seen = {focus_person}
    while desc_q:
        p = desc_q.popleft()
        for ch in p.children:
            if _known(ch) and ch not in desc_seen:
                desc_seen.add(ch)
                _set(ch, 4)
                desc_q.append(ch)

    # Snapshot of the core bloodline (Tiers 4 & 5 only) to process secondary connections.
    bloodline = set(priority.keys())

    # ── Tier 3: Partners of any core bloodline member ──
    for p in bloodline:
        if p.partner and _known(p.partner):
            _set(p.partner, 3)

    # ── Tier 3: Focus person's siblings + their partners ──
    focus_siblings = set()
    for par in focus_person.parents:
        for sib in par.children:
            if sib is not focus_person and _known(sib):
                focus_siblings.add(sib)
                _set(sib, 3)
                if sib.partner and _known(sib.partner):
                    _set(sib.partner, 3)

    # ── Tier 3: Aunts/uncles (parents' siblings) + first cousins (their children) ──
    first_cousins = set()
    for par in focus_person.parents:
        if not is_expanded(par):
            continue
        for gpar in par.parents:               # Grandparents
            if not _known(gpar):
                continue
            for aunt_uncle in gpar.children:   # Parents' siblings
                if aunt_uncle is par or not _known(aunt_uncle):
                    continue
                _set(aunt_uncle, 3)
                if aunt_uncle.partner and _known(aunt_uncle.partner):
                    _set(aunt_uncle.partner, 3)
                for cousin in aunt_uncle.children:    # First cousins
                    if _known(cousin):
                        first_cousins.add(cousin)
                        _set(cousin, 3)

    # ── Tier 2: Nieces & nephews (siblings' children) + grand-nieces/nephews (Tier 1) ──
    for sib in focus_siblings:
        for nn in sib.children:
            if _known(nn):
                _set(nn, 2)
                if nn.partner and _known(nn.partner):
                    _set(nn.partner, 2)
                for gnn in nn.children:        # Grand-nieces/nephews
                    if _known(gnn):
                        _set(gnn, 1)

    # ── Tier 2: First cousins' partners + second cousins (cousins' children) ──
    for cousin in first_cousins:
        if cousin.partner and _known(cousin.partner):
            _set(cousin.partner, 2)
        for sc in cousin.children:             # Second cousins
            if _known(sc):
                _set(sc, 2)
                if sc.partner and _known(sc.partner):
                    _set(sc.partner, 1)

    # ── Tier 2: Immediate in-laws (focus's partner's parents) + partner's siblings (Tier 1) ──
    if focus_person.partner and _known(focus_person.partner):
        for spar in focus_person.partner.parents:
            if _known(spar):
                _set(spar, 2)
                for ssib in spar.children:     # Partner's siblings
                    if ssib is not focus_person.partner and _known(ssib):
                        _set(ssib, 1)

    # ── Progressive culling ──
    # Sort all candidates by descending priority (tier 5 first, tier 1 last).
    all_candidates = sorted(priority.items(), key=lambda kv: -kv[1])

    # If the number of candidates fits under the budget, display all of them.
    if len(all_candidates) <= max_visible:
        return {p for p, _ in all_candidates}

    # Otherwise, drop the lowest tiers one by one until the candidate count is under max_visible.
    # We loop down from Tier 5 to Tier 3. We never cull below Tier 3 (Tiers 4 & 5 are preserved).
    visible = set()
    for min_tier in range(5, 2, -1):
        visible = {p for p, pri in all_candidates if pri >= min_tier}
        if len(visible) <= max_visible:
            break
    return visible
