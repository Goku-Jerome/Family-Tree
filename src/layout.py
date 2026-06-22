import collections
from person import Person

# ─────────────────────────────────────────────────────────────────────────────
#  Layout constants (derived from visually balanced proportions)
# ─────────────────────────────────────────────────────────────────────────────
NODE_W       = 140   # Width of a single person's card in pixels
NODE_H       =  56   # Height of a single person's card in pixels
H_GAP        =  30   # Minimum horizontal gap between cards/units on the same generation row
COUPLE_GAP   =  18   # Horizontal spacing between partners in a merged couple unit
GEN_H_GAP    = 100   # Vertical generational distance (between rows of parent/child units)
SUBTREE_PAD  =  12   # Extra horizontal buffer padding between independent sub-trees
LAYOUT_ITERS =   8   # Maximum passes to resolve overlaps and re-align parents to children

class FamilyUnit:
    """
    Job:
    ----
    Represents a single layout element (a block) in the family tree. A unit can contain
    either a single individual (e.g., unmarried, children, orphans) or a couple (partners).
    Grouping partners into a single unit ensures they stay side-by-side during layout.

    How it works:
    -------------
    - Keeps track of the X center coordinate and the top Y coordinate of the box.
    - Calculates the total layout width based on the number of members (1 or 2).
    - Exposes properties for boundary coordinates and anchor points used for connector line drawing.
    """
    def __init__(self, members):
        self.members = list(members)   # List containing 1 or 2 Person objects
        self.x = 0.0                   # X center coordinate of the unit
        self.y = 0.0                   # Top Y coordinate of the unit
        self.width = self._calc_width()

    def _calc_width(self):
        """Calculate unit width: one card width for single, or two cards + gap for couples."""
        n = len(self.members)
        return NODE_W * n + (COUPLE_GAP if n == 2 else 0)

    @property
    def left(self):  
        return self.x - self.width / 2

    @property
    def right(self): 
        return self.x + self.width / 2

    def top_centre(self):
        """Returns the (X, Y) coordinate at the center of the top edge (parent line entry)."""
        return (self.x, self.y)

    def bottom_centre(self):
        """Returns the (X, Y) coordinate at the center of the bottom edge (child line exit)."""
        return (self.x, self.y + NODE_H)

    def couple_mid_y(self):
        """Returns the Y coordinate of the horizontal line connecting partner cards."""
        return self.y + NODE_H / 2


def _order_couple(a: Person, b: Person) -> tuple:
    """
    Job:
    ----
    Determines which partner should be placed on the left (members[0]) and which
    on the right (members[1]) within a FamilyUnit.

    How it works:
    -------------
    Uses the ordering from shared children's `parents` list: the parent listed
    first (index 0) in any shared child's parents list is placed on the left.
    Falls back to alphabetical ID ordering if no shared children exist.
    """
    shared = [ch for ch in a.children if ch in b.children]
    if shared:
        ref_child = shared[0]
        if len(ref_child.parents) >= 2:
            if ref_child.parents[0] is b:
                return b, a
            elif ref_child.parents[0] is a:
                return a, b
    # Fallback: deterministic ordering by ID
    return (a, b) if a.id < b.id else (b, a)


def build_units(visible_people: set[Person], focus: Person = None) -> list[FamilyUnit]:
    """
    Job:
    ----
    Groups visible individuals into FamilyUnit instances. Partners who are both visible
    are merged into a single couple unit.

    How it works:
    -------------
    Iterates through visible people in deterministic order (sorted by ID). For each person:
    - If they or their partner are already grouped, skip.
    - If they have a partner who is also currently visible, they are bundled together.
      The couple's internal ordering (left vs right member) is determined by _order_couple(),
      which uses their shared children's parents list to ensure consistent placement.
    - Otherwise, they are created as a single-member unit.
    """
    assigned = set()
    units = []
    # Sort by ID for deterministic iteration (set ordering is arbitrary)
    sorted_people = sorted(visible_people, key=lambda p: p.id)
    for p in sorted_people:
        if p.id in assigned:
            continue
        if p.partner and p.partner in visible_people and p.partner.id not in assigned:
            p1, p2 = _order_couple(p, p.partner)
            unit = FamilyUnit([p1, p2])
            assigned.add(p.id)
            assigned.add(p.partner.id)
        else:
            unit = FamilyUnit([p])
            assigned.add(p.id)
        units.append(unit)
    return units


def assign_generations(visible_people: set[Person], focus: Person) -> dict[Person, int]:
    """
    Job:
    ----
    Assigns an integer generation level to each visible person relative to the focus person (Gen 0).
    Negative numbers denote older generations (parents = -1, grandparents = -2).
    Positive numbers denote younger generations (children = +1, grandchildren = +2).

    How it works:
    -------------
    Performs a standard Breadth-First Search (BFS) starting from the focus person:
    1. Focus is added to queue at generation level 0.
    2. Dequeues next person, checks their parents (generation = current - 1), children (generation = current + 1),
       and partner (generation = current) and schedules them if visible and unvisited.
    3. Any disconnected people not reached by BFS are placed at generation 0 by default.
    """
    if not focus:
        # Fallback if no focus person
        return {p: 0 for p in visible_people}

    gen_map = {focus: 0}
    queue = collections.deque([focus])
    while queue:
        p = queue.popleft()
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
            
    # Handle disconnected family tree sections.
    for p in visible_people:
        if p not in gen_map:
            gen_map[p] = 0
    return gen_map


def layout_units(units: list[FamilyUnit], gen_map: dict[Person, int], focus: Person = None) -> dict[Person, FamilyUnit]:
    """
    Job:
    ----
    Main layout placement engine. It determines initial coordinates (X, Y) for every FamilyUnit.

    How it works:
    -------------
    1. Anchors the focus person's unit at (X=0.0, Y=generation_level_height).
    2. Lays out children symmetrically below them. The width required by children is cached.
    3. Lays out parents split left/right above them (Paternal side on the left, Maternal on the right).
    4. Positions disconnected segments (orphans) to the far right.
    5. Runs the multi-pass resolver to push overlaps apart and align parent boxes over children.
    6. Re-centers everything so the focus unit stays as close to X=0.0 as possible.
    """
    # Create lookup map from Person -> FamilyUnit
    p2u = {}
    for u in units:
        for m in u.members:
            p2u[m] = u

    # Utility to get average generation level of a FamilyUnit
    def unit_gen(u):
        gens = [gen_map.get(m, 0) for m in u.members]
        return round(sum(gens) / len(gens))

    u_gen = {u: unit_gen(u) for u in units}
    min_gen = min(u_gen.values()) if u_gen else 0

    # Gets children units that reside in a younger generation level
    def child_units(u):
        """Returns child units in the order they appear in the parents' children lists."""
        seen = set()
        ordered = []
        for m in u.members:
            for ch in m.children:
                if ch in p2u:
                    cu = p2u[ch]
                    if cu not in seen and u_gen[cu] > u_gen[u]:
                        seen.add(cu)
                        ordered.append(cu)
        return ordered

    # Gets parent units that reside in an older generation level
    def parent_units(u):
        pu = set()
        for m in u.members:
            for par in m.parents:
                if par in p2u:
                    pu.add(p2u[par])
        return [p for p in pu if u_gen[p] < u_gen[u]]

    # Width caching for subtree downward sweeps
    down_cache = {}
    def down_width(u, _visiting=frozenset()):
        """Width needed by unit u and all its children/descendants below it."""
        if u in down_cache:
            return down_cache[u]
        if u in _visiting:               # Cycle guard
            return u.width + SUBTREE_PAD
        _v = _visiting | {u}
        children = child_units(u)
        if not children:
            w = u.width + SUBTREE_PAD
        else:
            w = max(u.width + SUBTREE_PAD,
                    sum(down_width(c, _v) for c in children))
        down_cache[u] = w
        return w

    # Placement coordinates map
    placed = set()
    u_x = {}
    u_y = {}

    # Converts integer generation level index to Y coordinate
    def y_for_gen(g):
        return (g - min_gen) * (NODE_H + GEN_H_GAP)

    # Places children symmetrically centered below the parent unit X coordinate
    def place_children(u):
        children = [c for c in child_units(u) if c not in placed]
        if not children:
            return
        total_w = sum(down_width(c) for c in children)
        x_cursor = u_x[u] - total_w / 2
        for c in children:
            sw = down_width(c)
            cx = x_cursor + sw / 2
            if c not in placed:
                u_x[c] = cx
                u_y[c] = y_for_gen(u_gen[c])
                placed.add(c)
            place_children(c)
            x_cursor += sw

    # Gets ideal centered X coordinate for parent unit based on their children's positions
    def anchored_parent_x(parent_unit):
        child_positions = [u_x[c] for c in child_units(parent_unit) if c in u_x]
        if child_positions:
            return sum(child_positions) / len(child_positions)
        return None

    # Recursively places parents above a unit
    def place_parents(u, visited=None):
        if visited is None:
            visited = set()
        if u in visited:
            return
        visited.add(u)

        parents = [p for p in parent_units(u) if p not in placed]
        if not parents:
            return

        # If only one parent is visible, center them directly above
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

        # Determine which parent unit corresponds to left side (paternal) and right side (maternal)
        def parent_side(pu):
            is_right = member_right is not None and any(m in member_right.parents for m in pu.members)
            is_left  = member_left  is not None and any(m in member_left.parents  for m in pu.members)
            if is_right and not is_left:
                return 'right'
            return 'left'

        left_parents  = [p for p in parents if parent_side(p) == 'left']
        right_parents = [p for p in parents if parent_side(p) == 'right']

        # Place left and right sub-trees relative to the center unit's X position
        def place_side(side_parents, direction):
            if not side_parents:
                return
            # Start from the edge of the current unit (not center) to avoid
            # children of the placed parent overlapping with the current unit.
            if direction == -1:
                x_cursor = u_x[u] - u.width / 2 - H_GAP
            else:
                x_cursor = u_x[u] + u.width / 2 + H_GAP
            for p in side_parents:
                if p in u_x:
                    continue
                # Use the width needed by unplaced children to ensure they have room
                unplaced_ch = [c for c in child_units(p) if c not in placed]
                if unplaced_ch:
                    width = max(p.width + SUBTREE_PAD,
                               sum(down_width(c) for c in unplaced_ch))
                else:
                    width = max(p.width + SUBTREE_PAD, NODE_W)
                if direction == -1: # Left
                    x_cursor -= width / 2
                    u_x[p] = x_cursor
                    x_cursor -= width / 2 + H_GAP
                else: # Right
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

    # ── Initial placement seeding ──
    # Select the focus person's unit as the anchor seed
    focus_unit = None
    if focus is not None and focus in p2u:
        focus_unit = p2u[focus]

    if focus_unit is None and units:
        # Fallback to the unit closest to generation 0
        focus_unit = min(units, key=lambda u: abs(unit_gen(u)))

    if focus_unit:
        u_x[focus_unit] = 0.0
        u_y[focus_unit] = y_for_gen(u_gen[focus_unit])
        placed.add(focus_unit)
        place_children(focus_unit)
        place_parents(focus_unit)

    # ── Position disconnected (orphan) segments ──
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

    # ── Overlap Resolution & Parent Re-anchoring ──
    resolve_overlaps_and_reanchor(units, u_x, u_y, u_gen, child_units, LAYOUT_ITERS)

    # Re-center so the focus unit doesn't drift away from X = 0.0
    if focus_unit and focus_unit in u_x:
        drift = u_x[focus_unit]
        if abs(drift) > 1.0:
            for u in units:
                u_x[u] -= drift

    # Write positions back to unit objects
    for u in units:
        u.x = u_x[u]
        u.y = u_y[u]

    return p2u


def resolve_overlaps_and_reanchor(units, u_x, u_y, u_gen, child_units_fn, max_iter=8):
    """
    Job:
    ----
    Ensures that cards on the same generational row do not overlap and that parents
    stay visually centered over their children.

    How it works:
    -------------
    Repeats up to max_iter times:
    - Pass A (Row Sweeping): For each row (sorted by X), pushes cards right if they overlap
      the card to their left, and then pushes them left if they overlap the card on their right.
      Minimum horizontal gap is NODE_W + H_GAP.
    - Pass B (Parent Re-centering): Bottom-up traversal. Calculates the average child position
      for each parent unit, and centers the parent above them if doing so does not create 
      new overlap conflicts on that parent's row.
    """
    if not units:
        return

    # Group units by generation row
    rows = collections.defaultdict(list)
    for u in units:
        rows[u_gen[u]].append(u)
    sorted_gens = sorted(rows.keys())

    for _iteration in range(max_iter):
        changed = False

        # ── Pass A: Row sweeping (Left-to-Right then Right-to-Left nudge) ──
        for gen in sorted_gens:
            row = sorted(rows[gen], key=lambda u: u_x[u])
            if len(row) < 2:
                continue

            # Push left-to-right
            for i in range(1, len(row)):
                prev, curr = row[i - 1], row[i]
                min_cx = u_x[prev] + prev.width / 2 + H_GAP + curr.width / 2
                if u_x[curr] < min_cx - 0.5:
                    shift = min_cx - u_x[curr]
                    for j in range(i, len(row)):
                        u_x[row[j]] += shift
                    changed = True

            # Push right-to-left
            for i in range(len(row) - 2, -1, -1):
                curr, nxt = row[i], row[i + 1]
                max_cx = u_x[nxt] - nxt.width / 2 - H_GAP - curr.width / 2
                if u_x[curr] > max_cx + 0.5:
                    shift = u_x[curr] - max_cx
                    for j in range(i + 1):
                        u_x[row[j]] -= shift
                    changed = True

        # ── Pass B: Parent re-anchoring (Youngest-to-Oldest row traversal) ──
        for gen in reversed(sorted_gens):
            for u in rows[gen]:
                children = [c for c in child_units_fn(u) if c in u_x]
                if not children:
                    continue
                ideal_x = sum(u_x[c] for c in children) / len(children)
                if abs(ideal_x - u_x[u]) < 0.5:
                    continue

                row = sorted(rows[gen], key=lambda u2: u_x[u2])
                try:
                    idx = row.index(u)
                except ValueError:
                    continue

                half = u.width / 2
                left_ok = (idx == 0 or
                           ideal_x - half >=
                           u_x[row[idx - 1]] + row[idx - 1].width / 2 + H_GAP - 0.5)
                right_ok = (idx == len(row) - 1 or
                            ideal_x + half <=
                            u_x[row[idx + 1]] - row[idx + 1].width / 2 - H_GAP + 0.5)

                if left_ok and right_ok:
                    u_x[u] = ideal_x
                    changed = True

        # Exit early if layout has stabilized (no modifications made in this iteration)
        if not changed:
            break


def compute_layout(visible_people: set[Person], focus_person: Person = None, layout_iters: int = 8) -> tuple[list[FamilyUnit], dict[Person, FamilyUnit]]:
    """
    Job:
    ----
    High-level layout entry point. Groups visible people, calculates their generation levels,
    computes non-overlapping spatial positions, and returns the positioned FamilyUnit objects.

    Returns:
    --------
    - list[FamilyUnit]: List of all computed FamilyUnit blocks.
    - dict[Person, FamilyUnit]: Mapping from Person object to their corresponding FamilyUnit block.
    """
    units = build_units(visible_people, focus=focus_person)
    gen_map = assign_generations(visible_people, focus_person)
    p2u = layout_units(units, gen_map, focus=focus_person)
    return units, p2u
