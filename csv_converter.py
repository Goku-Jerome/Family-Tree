import csv
import json
import uuid

def clean_date(year, month, day):
    """Formats the date to YYYY-MM-DD, or returns 'Unknown'."""
    if year and month and day:
        try:
            return f"{year}-{int(month):02d}-{int(day):02d}"
        except ValueError:
            pass
    return "Unknown"

# 1. Load your existing JSON data
with open('family_tree.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

existing_people = data.get("people", [])

# Map existing people by their full name so we can reuse your existing UUIDs
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

    # If they already exist in your JSON, map the CSV ID to their current UUID
    if full_name in existing_by_name:
        csv_id_to_uuid[csv_id] = existing_by_name[full_name]
    else:
        # Otherwise, generate a fresh UUID for the new entry
        csv_id_to_uuid[csv_id] = str(uuid.uuid4())

# 3. Second Pass: Build the data objects for the missing people
for row in rows:
    csv_id = row.get('ID', '').strip()
    if not csv_id: 
        continue

    person_uuid = csv_id_to_uuid[csv_id]

    # Only build a new dictionary if we didn't already load them from your JSON
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

# 4. Third Pass: Wire up the 'children' arrays
# We clear existing children arrays and rebuild them dynamically to ensure 100% accuracy
for p_id, person in all_people_dict.items():
    person['children'] = []

for p_id, person in all_people_dict.items():
    for parent_id in person.get('parents', []):
        if parent_id in all_people_dict:
            if p_id not in all_people_dict[parent_id]['children']:
                all_people_dict[parent_id]['children'].append(p_id)

# 5. Export the finalized layout
final_data = {"people": list(all_people_dict.values())}

with open('family_tree_complete.json', 'w', encoding='utf-8') as f:
    json.dump(final_data, f, indent=2)

print(f"Successfully merged! Saved to family_tree_complete.json.")
print(f"Total family members processed: {len(final_data['people'])}")