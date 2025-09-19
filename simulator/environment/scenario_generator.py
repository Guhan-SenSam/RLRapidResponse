"""
Scenario Generator - Step 1.2

Generates random MCI scenarios with casualties and ambulances.
"""

import json
import numpy as np
from typing import List, Dict, Tuple, Optional


class ScenarioGenerator:
    """
    Generates random mass casualty incident scenarios.

    Attributes:
        hospitals: List of hospital dictionaries
        region_bounds: Tuple of (min_lat, max_lat, min_lon, max_lon)
        rng: NumPy random number generator
    """

    def __init__(self, hospitals: List[Dict], region_bounds: Tuple[float, float, float, float], seed: Optional[int] = None):
        """
        Initialize the scenario generator.

        Args:
            hospitals: List of hospital dictionaries from hospital_loader
            region_bounds: (min_lat, max_lat, min_lon, max_lon) for the region
            seed: Random seed for reproducibility
        """
        self.hospitals = hospitals
        self.region_bounds = region_bounds
        self.rng = np.random.default_rng(seed)

        # Triage distribution based on START system
        self.triage_levels = ['RED', 'YELLOW', 'GREEN', 'BLACK']
        self.triage_probabilities = [0.25, 0.40, 0.30, 0.05]  # 25% Red, 40% Yellow, 30% Green, 5% Black

    def generate_scenario(
        self,
        num_casualties: int,
        ambulances_per_hospital: int = 2,
        ambulances_per_hospital_variation: int = 1,
        field_ambulances: int = 3,
        field_ambulance_radius_km: float = 10.0,
        seed: Optional[int] = None
    ) -> Dict:
        """
        Generate a random MCI scenario configuration.

        Note: Ambulances are NOT generated here - only the configuration for spawning them.
        The simulation engine will spawn ambulances dynamically based on this config.

        Args:
            num_casualties: Number of casualties to generate (50-80 recommended)
            ambulances_per_hospital: Base number of ambulances stationed at each hospital
            ambulances_per_hospital_variation: Random variation (+/-) in ambulances per hospital
            field_ambulances: Number of ambulances randomly placed near incident (first responders)
            field_ambulance_radius_km: Radius in km for field ambulance placement around incident
            seed: Optional seed for ambulance spawning reproducibility (uses scenario RNG if None)

        Returns:
            Scenario dictionary with structure:
            {
                'incident_location': [lat, lon],
                'casualties': [
                    {'id': 0, 'lat': ..., 'lon': ..., 'triage': 'RED', 'initial_health': 1.0},
                    ...
                ],
                'ambulance_config': {
                    'ambulances_per_hospital': int,
                    'ambulances_per_hospital_variation': int,
                    'field_ambulances': int,
                    'field_ambulance_radius_km': float,
                    'seed': int  # For reproducible spawning
                },
                'hospitals': [...],  # From hospital loader
                'timestamp': 0,
                'num_casualties': int
            }
        """
        min_lat, max_lat, min_lon, max_lon = self.region_bounds

        # Generate random incident location within region bounds
        incident_lat = self.rng.uniform(min_lat, max_lat)
        incident_lon = self.rng.uniform(min_lon, max_lon)
        incident_location = [incident_lat, incident_lon]

        # Generate casualties around incident location
        casualties = self._generate_casualties(num_casualties, incident_lat, incident_lon)

        # Store ambulance configuration (not actual ambulances)
        # Simulation engine will spawn them lazily
        ambulance_config = {
            'ambulances_per_hospital': ambulances_per_hospital,
            'ambulances_per_hospital_variation': ambulances_per_hospital_variation,
            'field_ambulances': field_ambulances,
            'field_ambulance_radius_km': field_ambulance_radius_km,
            'seed': seed if seed is not None else self.rng.integers(0, 2**31)
        }

        scenario = {
            'incident_location': incident_location,
            'casualties': casualties,
            'ambulance_config': ambulance_config,
            'hospitals': self.hospitals,
            'timestamp': 0,
            'num_casualties': num_casualties
        }

        return scenario

    def _generate_casualties(self, num_casualties: int, center_lat: float, center_lon: float) -> List[Dict]:
        """
        Generate casualties clustered around incident location using Gaussian distribution.

        Args:
            num_casualties: Number of casualties to generate
            center_lat: Incident center latitude
            center_lon: Incident center longitude

        Returns:
            List of casualty dictionaries
        """
        casualties = []

        # Standard deviation for Gaussian distribution (approximately 500m)
        # Using approximate conversion: 1 degree latitude ≈ 111 km
        # So 500m ≈ 0.0045 degrees
        sigma_lat = 0.0045
        sigma_lon = 0.0045

        # Generate triage levels for all casualties
        triage_assignments = self.rng.choice(
            self.triage_levels,
            size=num_casualties,
            p=self.triage_probabilities
        )

        for i in range(num_casualties):
            # Generate position using Gaussian distribution around incident
            casualty_lat = self.rng.normal(center_lat, sigma_lat)
            casualty_lon = self.rng.normal(center_lon, sigma_lon)

            casualty = {
                'id': i,
                'lat': casualty_lat,
                'lon': casualty_lon,
                'triage': triage_assignments[i],
                'initial_health': 1.0,  # All start at full health
            }

            casualties.append(casualty)

        return casualties

    def spawn_ambulances(
        self,
        incident_location: List[float],
        ambulance_config: Dict,
        hospitals: List[Dict]
    ) -> List[Dict]:
        """
        Spawn ambulances based on configuration (called by simulation engine).

        This method creates ambulances dynamically at simulation start rather than
        storing them in the scenario JSON.

        Args:
            incident_location: [lat, lon] of incident
            ambulance_config: Configuration dict with keys:
                - ambulances_per_hospital: Base count per hospital
                - ambulances_per_hospital_variation: Random variation (+/-)
                - field_ambulances: Number of field units
                - field_ambulance_radius_km: Radius for field unit placement
                - seed: Random seed for reproducibility
            hospitals: List of hospital dictionaries

        Returns:
            List of ambulance dictionaries with 'base_hospital_id' field
        """
        # Create RNG with config seed for reproducibility
        rng = np.random.default_rng(ambulance_config['seed'])

        ambulances = []
        ambulance_id = 0

        incident_lat, incident_lon = incident_location

        # 1. Generate hospital-based ambulances
        for hospital in hospitals:
            # Calculate number of ambulances for this hospital with variation
            variation_range = ambulance_config['ambulances_per_hospital_variation']
            if variation_range > 0:
                variation = rng.integers(-variation_range, variation_range + 1)
                num_hospital_ambulances = max(0, ambulance_config['ambulances_per_hospital'] + variation)
            else:
                num_hospital_ambulances = ambulance_config['ambulances_per_hospital']

            # Create ambulances stationed at this hospital
            for _ in range(num_hospital_ambulances):
                ambulance = {
                    'id': ambulance_id,
                    'lat': hospital['lat'],
                    'lon': hospital['lon'],
                    'status': 'IDLE',
                    'base_hospital_id': hospital['id'],
                    'type': 'HOSPITAL_BASED'
                }
                ambulances.append(ambulance)
                ambulance_id += 1

        # 2. Generate field ambulances (first responders near incident)
        # Convert km radius to degrees (approximately 1 degree ≈ 111 km)
        radius_deg = ambulance_config['field_ambulance_radius_km'] / 111.0

        for _ in range(ambulance_config['field_ambulances']):
            # Generate random position within radius using uniform distribution in polar coordinates
            # Use sqrt for uniform spatial distribution (avoids clustering at center)
            r = radius_deg * np.sqrt(rng.uniform(0, 1))
            theta = rng.uniform(0, 2 * np.pi)

            ambulance_lat = incident_lat + r * np.cos(theta)
            ambulance_lon = incident_lon + r * np.sin(theta)

            ambulance = {
                'id': ambulance_id,
                'lat': ambulance_lat,
                'lon': ambulance_lon,
                'status': 'IDLE',
                'base_hospital_id': None,
                'type': 'FIELD_UNIT'
            }
            ambulances.append(ambulance)
            ambulance_id += 1

        return ambulances

    def save_scenario(self, scenario: Dict, filename: str) -> None:
        """
        Save scenario to JSON file.

        Args:
            scenario: Scenario dictionary from generate_scenario()
            filename: Output filename (e.g., 'scenario_001.json')
        """
        with open(filename, 'w') as f:
            json.dump(scenario, f, indent=2)

    def load_scenario(self, filename: str) -> Dict:
        """
        Load scenario from JSON file.

        Args:
            filename: Input filename

        Returns:
            Scenario dictionary
        """
        with open(filename, 'r') as f:
            scenario = json.load(f)
        return scenario


def calculate_region_bounds(hospitals: List[Dict], padding: float = 0.1) -> Tuple[float, float, float, float]:
    """
    Calculate region bounds from hospital locations with optional padding.

    Args:
        hospitals: List of hospital dictionaries
        padding: Padding in degrees to add around bounds (default 0.1 ≈ 11km)

    Returns:
        Tuple of (min_lat, max_lat, min_lon, max_lon)
    """
    if not hospitals:
        raise ValueError("Hospital list is empty")

    lats = [h['lat'] for h in hospitals]
    lons = [h['lon'] for h in hospitals]

    min_lat = min(lats) - padding
    max_lat = max(lats) + padding
    min_lon = min(lons) - padding
    max_lon = max(lons) + padding

    return (min_lat, max_lat, min_lon, max_lon)


if __name__ == '__main__':
    # Test scenario generation
    from hospital_loader import load_hospitals

    print("Testing Scenario Generator...")
    print("=" * 60)

    # Load hospitals for California
    print("\n1. Loading California hospitals...")
    hospitals = load_hospitals(region='CA')
    print(f"   Loaded {len(hospitals)} hospitals")

    # Calculate region bounds
    print("\n2. Calculating region bounds...")
    region_bounds = calculate_region_bounds(hospitals)
    print(f"   Region bounds: {region_bounds}")
    print(f"   Lat range: {region_bounds[0]:.4f} to {region_bounds[1]:.4f}")
    print(f"   Lon range: {region_bounds[2]:.4f} to {region_bounds[3]:.4f}")

    # Create scenario generator
    print("\n3. Creating scenario generator...")
    generator = ScenarioGenerator(hospitals, region_bounds, seed=42)

    # Generate test scenarios
    print("\n4. Generating 10 test scenarios...")
    triage_totals = {'RED': 0, 'YELLOW': 0, 'GREEN': 0, 'BLACK': 0}
    total_casualties = 0

    for i in range(10):
        scenario = generator.generate_scenario(
            num_casualties=np.random.randint(50, 81),
            ambulances_per_hospital=2,
            ambulances_per_hospital_variation=1,
            field_ambulances=3,
            field_ambulance_radius_km=10.0
        )

        # Count triage levels
        for casualty in scenario['casualties']:
            triage_totals[casualty['triage']] += 1
            total_casualties += 1

        # Display ambulance config (not actual ambulances)
        config = scenario['ambulance_config']
        print(f"   Scenario {i+1}: {scenario['num_casualties']} casualties, "
              f"ambulance config: {config['ambulances_per_hospital']}±{config['ambulances_per_hospital_variation']} per hospital + "
              f"{config['field_ambulances']} field units at "
              f"({scenario['incident_location'][0]:.4f}, {scenario['incident_location'][1]:.4f})")

    # Verify triage distribution
    print("\n5. Verifying triage distribution across all scenarios...")
    print(f"   Total casualties: {total_casualties}")
    for triage in ['RED', 'YELLOW', 'GREEN', 'BLACK']:
        actual_pct = (triage_totals[triage] / total_casualties) * 100
        expected_pct = {'RED': 25, 'YELLOW': 40, 'GREEN': 30, 'BLACK': 5}[triage]
        print(f"   {triage:6s}: {triage_totals[triage]:4d} ({actual_pct:5.1f}%) - Expected: {expected_pct}%")

    # Test save/load
    print("\n6. Testing save/load functionality...")
    test_scenario = generator.generate_scenario(
        num_casualties=60,
        ambulances_per_hospital=2,
        ambulances_per_hospital_variation=1,
        field_ambulances=5,
        field_ambulance_radius_km=10.0,
        seed=123
    )
    generator.save_scenario(test_scenario, 'test_scenario.json')
    loaded_scenario = generator.load_scenario('test_scenario.json')

    assert test_scenario['num_casualties'] == loaded_scenario['num_casualties']
    assert test_scenario['ambulance_config'] == loaded_scenario['ambulance_config']
    assert len(test_scenario['casualties']) == len(loaded_scenario['casualties'])
    print("   Save/load test: PASS")
    print(f"   Scenario JSON file size reduced (no ambulances stored)")

    # Show sample scenario structure
    print("\n7. Sample scenario structure (lazy ambulance spawning):")
    print(f"   Incident location: {test_scenario['incident_location']}")
    print(f"   Number of casualties: {len(test_scenario['casualties'])}")
    print(f"   Number of hospitals: {len(test_scenario['hospitals'])}")
    print(f"   Ambulance config: {test_scenario['ambulance_config']}")

    print(f"\n   Sample casualty: {test_scenario['casualties'][0]}")

    # Test ambulance spawning
    print("\n8. Testing ambulance spawning (simulation initialization)...")
    spawned_ambulances = generator.spawn_ambulances(
        test_scenario['incident_location'],
        test_scenario['ambulance_config'],
        test_scenario['hospitals']
    )

    # Count ambulance types
    hospital_based = [a for a in spawned_ambulances if a['type'] == 'HOSPITAL_BASED']
    field_units = [a for a in spawned_ambulances if a['type'] == 'FIELD_UNIT']

    print(f"   Spawned {len(spawned_ambulances)} total ambulances")
    print(f"   Hospital-based: {len(hospital_based)}")
    print(f"   Field units: {len(field_units)}")
    print(f"   Sample hospital-based ambulance: {hospital_based[0]}")
    print(f"   Sample field unit ambulance: {field_units[0]}")

    # Test reproducibility
    spawned_ambulances_2 = generator.spawn_ambulances(
        test_scenario['incident_location'],
        test_scenario['ambulance_config'],
        test_scenario['hospitals']
    )
    assert len(spawned_ambulances) == len(spawned_ambulances_2)
    assert spawned_ambulances[0] == spawned_ambulances_2[0]
    print("   Reproducibility test: PASS (same seed → same ambulances)")

    print("\n" + "=" * 60)
    print("✓ All tests passed!")
