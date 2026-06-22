# csv_converter.py
#
# Job:
# ----
# This is a standalone utility script designed to import external genealogical data from
# a CSV file and merge it into the main family tree database ('family_tree.json').
# It generates the combined result and saves it to 'family_tree_complete.json'.
#
# How it works:
# -------------
# 1. Loads current database: Reads existing person entries from 'family_tree.json' so it can
#    keep existing unique IDs (UUIDs) for people already in the system.
# 2. First Pass (CSV Reading & ID Map): Reads rows from 'My-Family-*.csv'. For each row,
#    it maps the CSV's numeric/text ID to the person's existing UUID (if their name matches
#    someone already in the system) or generates a new random UUID.
# 3. Second Pass (Object Hydration): Constructs JSON-serializable dictionaries for all individuals,
#    including formatting dates to standard YYYY-MM-DD.
# 4. Third Pass (Bidirectional Wiring): Rebuilds 'children' arrays for all records by scanning
#    the 'parents' keys and back-linking them to ensure relationship pointers remain 100% accurate.
# 5. Export: Dumps the final list of people into 'family_tree_complete.json'.

import csv
import json
import uuid

def clean_date(year: str, month: str, day: str) -> str:
    """
    Job:
    ----
    Formats date parts into a standardized 'YYYY-MM-DD' string.
    Returns 'Unknown' if date components are missing or invalid.
    """
    if year and month and day:
        try:
            return f"{year}-{int(month):02d}-{int(day):02d}"
        except ValueError:
            pass
    return "Unknown"

# 1. Load existing JSON data to preserve current UUID keys
with open('family_tree.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

existing_people = data.get("people", [])

# Map existing people by full name to enable ID reuse and avoid duplicate entries
existing_by_name = {}
for p in existing_people:
    full_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
    existing_by_name[full_name] = p['id']

csv_id_to_uuid = {}
all_people_dict = {p['id']: p for p in existing_people}

# 2. First Pass: Read the CSV, identify new people, and map their CSV IDs to UUIDs
with open('My-Family-30-Mar-2026-190211558.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

for row in rows:
    csv_id = row.get('ID', '').strip()
    if not csv_id: 
        continue

    first_name = row.get('Given names', '').strip()
    last_name = row.get('Surname now', '').strip()
    if not last_name:
        last_name = row.get('Surname at birth', '').strip()
    
    full_name = f"{first_name} {last_name}".strip()

    # If the person already exists in current JSON, match CSV ID to their current UUID
    if full_name in existing_by_name:
        csv_id_to_uuid[csv_id] = existing_by_name[full_name]
    else:
        # Generate a new UUID for a new entry
        csv_id_to_uuid[csv_id] = str(uuid.uuid4())

# 3. Second Pass: Build the data objects for missing individuals
for row in rows:
    csv_id = row.get('ID', '').strip()
    if not csv_id: 
        continue

    person_uuid = csv_id_to_uuid[csv_id]

    # Only create a new record if they are not already in the loaded JSON database
    if person_uuid not in all_people_dict:
        first_name = row.get('Given names', '').strip()
        last_name = row.get('Surname now', '').strip()
        if not last_name:
            last_name = row.get('Surname at birth', '').strip()
            
        dob = clean_date(row.get('Birth year'), row.get('Birth month'), row.get('Birth day'))
        gender = row.get('Gender', '').strip()
        if gender not in ["Male", "Female"]:
            gender = None

        parents = []
        if row.get('Mother ID') in csv_id_to_uuid:
            parents.append(csv_id_to_uuid[row.get('Mother ID')])
        if row.get('Father ID') in csv_id_to_uuid:
            parents.append(csv_id_to_uuid[row.get('Father ID')])

        partner = None
        if row.get('Partner ID') in csv_id_to_uuid:
            partner = csv_id_to_uuid[row.get('Partner ID')]

        new_person = {
            "id": person_uuid,
            "first_name": first_name,
            "last_name": last_name,
            "dob": dob,
            "gender": gender,
            "parents": parents,
            "children": [], 
            "partner": partner
        }
        all_people_dict[person_uuid] = new_person

# 4. Third Pass: Rebuild the children array links to guarantee consistency
for p_id, person in all_people_dict.items():
    person['children'] = []

for p_id, person in all_people_dict.items():
    for parent_id in person.get('parents', []):
        if parent_id in all_people_dict:
            if p_id not in all_people_dict[parent_id]['children']:
                all_people_dict[parent_id]['children'].append(p_id)

# 5. Export combined database to disk
final_data = {"people": list(all_people_dict.values())}

with open('family_tree_complete.json', 'w', encoding='utf-8') as f:
    json.dump(final_data, f, indent=2)

print(f"Successfully merged! Saved to family_tree_complete.json.")
print(f"Total family members processed: {len(final_data['people'])}")