"""
Generate benchmark scenarios for populated US locations.

This script creates standardized MCI scenarios at specific locations
for consistent testing and evaluation throughout the project.
"""

import os
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.environment.scenario_generator import ScenarioGenerator
from simulator.environment.hospital_loader import load_hospitals


def dms_to_decimal(degrees, minutes, seconds, direction):
    """
    Convert coordinates from degrees/minutes/seconds to decimal degrees.

    Args:
        degrees: Degrees value
        minutes: Minutes value
        seconds: Seconds value
        direction: 'N', 'S', 'E', or 'W'

    Returns:
        Decimal degrees (negative for S/W)
    """
    decimal = degrees + minutes / 60 + seconds / 3600
    if direction in ['S', 'W']:
        decimal = -decimal
    return decimal


# Define benchmark locations
BENCHMARK_LOCATIONS = {
    'tampa_1': {
        'name': 'Tampa 1',
        'lat': dms_to_decimal(27, 58, 55.5, 'N'),
        'lon': dms_to_decimal(82, 27, 48.7, 'W'),
        'region': 'FL',
        'description': 'Tampa Bay area - Location 1'
    },
    'tampa_2': {
        'name': 'Tampa 2',
        'lat': dms_to_decimal(27, 58, 0.9, 'N'),
        'lon': dms_to_decimal(82, 25, 48.0, 'W'),
        'region': 'FL',
        'description': 'Tampa Bay area - Location 2'
    }
}


def generate_benchmark_scenarios(
    output_dir: str = 'scenarios/benchmark',
    num_casualties: int = 60,
    ambulances_per_hospital: int = 2,
    ambulances_per_hospital_variation: int = 1,
    field_ambulances: int = 5,
    field_ambulance_radius_km: float = 10.0,
    seed: int = 42
):
    """
    Generate benchmark scenarios for all defined locations.

    Args:
        output_dir: Directory to save scenarios
        num_casualties: Number of casualties per scenario
        ambulances_per_hospital: Base number of ambulances per hospital
        ambulances_per_hospital_variation: Random variation in ambulances
        field_ambulances: Number of field ambulance units
        field_ambulance_radius_km: Radius for field ambulance placement
        seed: Random seed for reproducibility
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Track scenarios across regions
    scenarios_by_region = {}

    for location_id, location_info in BENCHMARK_LOCATIONS.items():
        region = location_info['region']

        # Load hospitals for this region (cache by region)
        if region not in scenarios_by_region:
            print(f"\nLoading hospitals for region: {region}")
            hospitals = load_hospitals(region=region)
            print(f"  Loaded {len(hospitals)} hospitals")
            scenarios_by_region[region] = hospitals
        else:
            hospitals = scenarios_by_region[region]

        # Create scenario generator with fixed incident location
        # We override region_bounds to center on our specific location
        lat, lon = location_info['lat'], location_info['lon']
        region_bounds = (lat - 0.01, lat + 0.01, lon - 0.01, lon + 0.01)

        generator = ScenarioGenerator(hospitals, region_bounds, seed=seed)

        # Generate scenario at exact location
        print(f"\nGenerating scenario: {location_info['name']}")
        print(f"  Location: ({lat:.6f}, {lon:.6f})")
        print(f"  Description: {location_info['description']}")

        scenario = generator.generate_scenario(
            num_casualties=num_casualties,
            ambulances_per_hospital=ambulances_per_hospital,
            ambulances_per_hospital_variation=ambulances_per_hospital_variation,
            field_ambulances=field_ambulances,
            field_ambulance_radius_km=field_ambulance_radius_km,
            seed=seed
        )

        # Override the incident location to our exact coordinates
        scenario['incident_location'] = [lat, lon]

        # Add metadata
        scenario['metadata'] = {
            'location_id': location_id,
            'location_name': location_info['name'],
            'description': location_info['description'],
            'region': region,
            'is_benchmark': True
        }

        # Save scenario
        filename = f"{location_id}.json"
        filepath = os.path.join(output_dir, filename)
        generator.save_scenario(scenario, filepath)

        # Get file size
        file_size_kb = os.path.getsize(filepath) / 1024

        print(f"  Casualties: {len(scenario['casualties'])}")
        print(f"  Hospitals in region: {len(scenario['hospitals'])}")
        print(f"  Ambulance config: {scenario['ambulance_config']['ambulances_per_hospital']}±"
              f"{scenario['ambulance_config']['ambulances_per_hospital_variation']} per hospital + "
              f"{scenario['ambulance_config']['field_ambulances']} field units")
        print(f"  Saved to: {filepath} ({file_size_kb:.1f} KB)")

        # Count triage distribution
        triage_counts = {'RED': 0, 'YELLOW': 0, 'GREEN': 0, 'BLACK': 0}
        for casualty in scenario['casualties']:
            triage_counts[casualty['triage']] += 1

        print(f"  Triage distribution:")
        for triage, count in triage_counts.items():
            pct = (count / len(scenario['casualties'])) * 100
            print(f"    {triage}: {count} ({pct:.1f}%)")

    # Create index file
    index = {
        'description': 'Benchmark scenarios for consistent testing',
        'generated_at': str(Path(output_dir).stat().st_mtime),
        'configuration': {
            'num_casualties': num_casualties,
            'ambulances_per_hospital': ambulances_per_hospital,
            'ambulances_per_hospital_variation': ambulances_per_hospital_variation,
            'field_ambulances': field_ambulances,
            'field_ambulance_radius_km': field_ambulance_radius_km,
            'seed': seed
        },
        'scenarios': {
            location_id: {
                'name': info['name'],
                'description': info['description'],
                'coordinates': [info['lat'], info['lon']],
                'region': info['region'],
                'filename': f"{location_id}.json"
            }
            for location_id, info in BENCHMARK_LOCATIONS.items()
        }
    }

    index_path = os.path.join(output_dir, 'index.json')
    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)

    print(f"\n{'='*60}")
    print(f"✓ Generated {len(BENCHMARK_LOCATIONS)} benchmark scenarios")
    print(f"✓ Saved to: {output_dir}/")
    print(f"✓ Index file: {index_path}")
    print(f"{'='*60}")


if __name__ == '__main__':
    print("Benchmark Scenario Generator")
    print("=" * 60)

    generate_benchmark_scenarios(
        output_dir='scenarios/benchmark',
        num_casualties=60,
        ambulances_per_hospital=2,
        ambulances_per_hospital_variation=1,
        field_ambulances=5,
        field_ambulance_radius_km=10.0,
        seed=42
    )
