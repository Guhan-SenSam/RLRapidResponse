"""
Hospital Data Loader - Step 1.1

Loads hospital data from CSV and provides filtering capabilities.
"""

import csv
from typing import List, Dict, Optional


def load_hospitals(region: Optional[str] = None) -> List[Dict]:
    """
    Load hospitals from the US hospital locations dataset.

    Args:
        region: Optional state abbreviation (e.g., "CA" for California).
                If None, loads all hospitals.

    Returns:
        List of hospital dictionaries with keys:
        - id: Hospital ID
        - lat: Latitude
        - lon: Longitude
        - beds: Number of beds (int, -999 if not available)
        - trauma_level: Integer 1-5 (1=Level I, 2=Level II, 3=Level III,
                        4=Level IV, 5=Not Available)
        - helipad: Boolean (True if helipad available)
    """
    hospitals = []
    csv_path = 'datasets/us_hospital_locations.csv'

    # Trauma level mapping
    trauma_mapping = {
        'LEVEL I': 1,
        'LEVEL II': 2,
        'LEVEL III': 3,
        'LEVEL IV': 4,
        'NOT AVAILABLE': 5,
        'LEVEL I PEDIATRIC': 1,  # Treat pediatric as same level
        'LEVEL II PEDIATRIC': 2,
    }

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Filter by region if specified
            if region and row['STATE'] != region:
                continue

            # Skip if missing critical data
            if not row['LATITUDE'] or not row['LONGITUDE']:
                continue

            # Parse trauma level
            trauma_str = row['TRAUMA'].strip().upper()
            trauma_level = trauma_mapping.get(trauma_str, 5)

            # Parse beds (handle -999 and NOT AVAILABLE)
            try:
                beds = int(row['BEDS'])
            except (ValueError, KeyError):
                beds = -999

            # Parse helipad
            helipad = row['HELIPAD'].strip().upper() == 'Y'

            hospital = {
                'id': row['ID'],
                'lat': float(row['LATITUDE']),
                'lon': float(row['LONGITUDE']),
                'beds': beds,
                'trauma_level': trauma_level,
                'helipad': helipad,
                'name': row['NAME'],
                'city': row['CITY'],
                'state': row['STATE']
            }

            hospitals.append(hospital)

    return hospitals


def get_hospital_by_id(hospitals: List[Dict], hospital_id: str) -> Optional[Dict]:
    """
    Retrieve a specific hospital by its ID.

    Args:
        hospitals: List of hospital dictionaries from load_hospitals()
        hospital_id: Hospital ID to search for

    Returns:
        Hospital dictionary if found, None otherwise
    """
    for hospital in hospitals:
        if hospital['id'] == hospital_id:
            return hospital
    return None


if __name__ == '__main__':
    # Test: Load California hospitals
    print("Loading California hospitals...")
    ca_hospitals = load_hospitals(region='CA')
    print(f"Loaded {len(ca_hospitals)} hospitals in California")

    # Verify trauma level mapping
    trauma_counts = {}
    for h in ca_hospitals:
        level = h['trauma_level']
        trauma_counts[level] = trauma_counts.get(level, 0) + 1

    print("\nTrauma level distribution:")
    for level in sorted(trauma_counts.keys()):
        level_name = {1: 'Level I', 2: 'Level II', 3: 'Level III',
                      4: 'Level IV', 5: 'Not Available'}[level]
        print(f"  {level_name}: {trauma_counts[level]} hospitals")

    # Test get_hospital_by_id
    if ca_hospitals:
        test_id = ca_hospitals[0]['id']
        found = get_hospital_by_id(ca_hospitals, test_id)
        print(f"\nTest get_hospital_by_id: {'PASS' if found else 'FAIL'}")
        if found:
            print(f"  Found: {found['name']} in {found['city']}")

    # Show sample hospital
    if ca_hospitals:
        print("\nSample hospital:")
        print(ca_hospitals[0])
