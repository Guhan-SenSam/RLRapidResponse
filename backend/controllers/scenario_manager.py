"""
Scenario Manager - Handles scenario generation, loading, and management
"""

import os
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
import sys

# Add parent directory to path to import simulator modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from simulator.environment.scenario_generator import ScenarioGenerator, calculate_region_bounds
from simulator.environment.hospital_loader import load_hospitals
from utils.json_utils import convert_numpy_types

logger = logging.getLogger(__name__)


class ScenarioManager:
    """Manages MCI scenario generation and storage"""

    def __init__(self, project_root: str):
        """
        Initialize scenario manager.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = project_root
        self.scenarios_dir = os.path.join(project_root, 'scenarios', 'generated')

        # Create scenarios directory if it doesn't exist
        os.makedirs(self.scenarios_dir, exist_ok=True)

        # Cache for hospitals by region
        self.hospital_cache = {}
        self.region_bounds_cache = {}

        logger.info(f"ScenarioManager initialized (scenarios_dir: {self.scenarios_dir})")

    def get_hospitals(self, region: str = 'CA') -> List[Dict]:
        """
        Load hospitals for a region with caching.

        Args:
            region: Region code (e.g., 'CA', 'FL', 'NY')

        Returns:
            List of hospital dictionaries
        """
        if region not in self.hospital_cache:
            hospitals = load_hospitals(region=region)
            self.hospital_cache[region] = hospitals
            logger.info(f"Loaded {len(hospitals)} hospitals for region {region}")

        return self.hospital_cache[region]

    def get_region_bounds(self, region: str = 'CA') -> tuple:
        """
        Calculate region bounds with caching.

        Args:
            region: Region code

        Returns:
            Tuple of (min_lat, max_lat, min_lon, max_lon)
        """
        if region not in self.region_bounds_cache:
            hospitals = self.get_hospitals(region)
            bounds = calculate_region_bounds(hospitals)
            self.region_bounds_cache[region] = bounds
            logger.info(f"Calculated bounds for region {region}: {bounds}")

        return self.region_bounds_cache[region]

    def generate_scenario(
        self,
        region: str = 'CA',
        num_casualties: int = 60,
        ambulances_per_hospital: int = 2,
        ambulances_per_hospital_variation: int = 1,
        field_ambulances: int = 5,
        field_ambulance_radius_km: float = 10.0,
        seed: Optional[int] = None,
        name: Optional[str] = None,
        save: bool = True,
        incident_location: Optional[List] = None,
        manual_ambulances: Optional[List[Dict]] = None,
        casualty_distribution_radius: float = 0.5
    ) -> Dict:
        """
        Generate a new MCI scenario.

        Args:
            region: Region code for hospital data
            num_casualties: Number of casualties (50-80 recommended)
            ambulances_per_hospital: Base ambulances per hospital
            ambulances_per_hospital_variation: Random variation (+/-)
            field_ambulances: Number of field first responders
            field_ambulance_radius_km: Radius for field ambulance placement
            seed: Random seed for reproducibility
            name: Optional scenario name
            save: Whether to save the scenario to disk
            incident_location: Optional manual incident location [lat, lon]
            manual_ambulances: Optional list of manually placed ambulances [{'lat': x, 'lon': y}, ...]
            casualty_distribution_radius: Radius in km for casualty distribution

        Returns:
            Generated scenario dictionary with metadata
        """
        hospitals = self.get_hospitals(region)
        region_bounds = self.get_region_bounds(region)

        # Create generator
        generator = ScenarioGenerator(hospitals, region_bounds, seed=seed)

        # Generate scenario
        if incident_location and manual_ambulances:
            # Manual mode: use provided incident location and ambulances
            scenario = generator.generate_scenario(
                num_casualties=num_casualties,
                incident_location=tuple(incident_location),
                manual_ambulances=manual_ambulances,
                seed=seed,
                casualty_distribution_radius=casualty_distribution_radius,
                ambulances_per_hospital=ambulances_per_hospital, # Pass these too even in manual mode for config record
                ambulances_per_hospital_variation=ambulances_per_hospital_variation
            )
        else:
            # Automatic mode: generate random scenario
            scenario = generator.generate_scenario(
                num_casualties=num_casualties,
                ambulances_per_hospital=ambulances_per_hospital,
                ambulances_per_hospital_variation=ambulances_per_hospital_variation,
                field_ambulances=field_ambulances,
                field_ambulance_radius_km=field_ambulance_radius_km,
                seed=seed,
                casualty_distribution_radius=casualty_distribution_radius
            )

        # Add metadata
        timestamp = datetime.now().isoformat()
        scenario_id = f"scenario_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        scenario['metadata'] = {
            'id': scenario_id,
            'name': name or scenario_id,
            'region': region,
            'generated_at': timestamp,
            'configuration': {
                'num_casualties': num_casualties,
                'ambulances_per_hospital': ambulances_per_hospital,
                'ambulances_per_hospital_variation': ambulances_per_hospital_variation,
                'field_ambulances': field_ambulances,
                'field_ambulance_radius_km': field_ambulance_radius_km,
                'seed': seed
            }
        }

        # Convert all numpy types to native python types for serialization
        scenario = convert_numpy_types(scenario)

        # Save if requested
        if save:
            filename = os.path.join(self.scenarios_dir, f"{scenario_id}.json")
            with open(filename, 'w') as f:
                json.dump(scenario, f, indent=2)
            scenario['metadata']['filename'] = filename
            logger.info(f"Saved scenario {scenario_id} to {filename}")

        return scenario

    def list_scenarios(self) -> List[Dict]:
        """
        List all saved scenarios with metadata.

        Returns:
            List of scenario metadata dictionaries
        """
        scenarios = []

        # Check generated scenarios
        if os.path.exists(self.scenarios_dir):
            for filename in os.listdir(self.scenarios_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.scenarios_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            scenario = json.load(f)

                        # Extract metadata
                        metadata = scenario.get('metadata', {})
                        metadata['filename'] = filepath
                        metadata['id'] = metadata.get('id', filename.replace('.json', ''))
                        metadata['num_casualties'] = scenario.get('num_casualties', 0)
                        metadata['incident_location'] = scenario.get('incident_location', [0, 0])

                        scenarios.append(metadata)
                    except Exception as e:
                        logger.error(f"Error loading scenario {filename}: {e}")

        # Also check benchmark scenarios
        benchmark_dir = os.path.join(self.project_root, 'scenarios', 'benchmark')
        if os.path.exists(benchmark_dir):
            index_file = os.path.join(benchmark_dir, 'index.json')
            if os.path.exists(index_file):
                try:
                    with open(index_file, 'r') as f:
                        index = json.load(f)

                    for scenario_key, scenario_info in index.get('scenarios', {}).items():
                        filepath = os.path.join(benchmark_dir, scenario_info['filename'])
                        if os.path.exists(filepath):
                            scenarios.append({
                                'id': scenario_key,
                                'name': scenario_info['name'],
                                'filename': filepath,
                                'region': scenario_info.get('region', 'FL'),
                                'incident_location': scenario_info.get('coordinates', [0, 0]),
                                'configuration': index.get('configuration', {}),
                                'is_benchmark': True
                            })
                except Exception as e:
                    logger.error(f"Error loading benchmark scenarios: {e}")

        return scenarios

    def load_scenario(self, scenario_id: str) -> Optional[Dict]:
        """
        Load a scenario by ID or filename.

        Args:
            scenario_id: Scenario ID or filename

        Returns:
            Scenario dictionary or None if not found
        """
        # Try generated scenarios
        filepath = os.path.join(self.scenarios_dir, f"{scenario_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)

        # Try benchmark scenarios
        benchmark_dir = os.path.join(self.project_root, 'scenarios', 'benchmark')
        filepath = os.path.join(benchmark_dir, f"{scenario_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)

        # Try direct filepath
        if os.path.exists(scenario_id):
            with open(scenario_id, 'r') as f:
                return json.load(f)

        logger.error(f"Scenario not found: {scenario_id}")
        return None

    def delete_scenario(self, scenario_id: str) -> bool:
        """
        Delete a scenario (only generated scenarios, not benchmarks).

        Args:
            scenario_id: Scenario ID

        Returns:
            True if deleted successfully
        """
        filepath = os.path.join(self.scenarios_dir, f"{scenario_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Deleted scenario {scenario_id}")
            return True

        logger.error(f"Scenario not found for deletion: {scenario_id}")
        return False

    def get_scenario_preview(self, scenario: Dict) -> Dict:
        """
        Get a lightweight preview of a scenario for visualization.

        Args:
            scenario: Full scenario dictionary

        Returns:
            Preview dictionary with essential data
        """
        # Count casualties by triage
        triage_counts = {'RED': 0, 'YELLOW': 0, 'GREEN': 0, 'BLACK': 0}
        for casualty in scenario.get('casualties', []):
            triage = casualty.get('triage', 'UNKNOWN')
            if triage in triage_counts:
                triage_counts[triage] += 1

        return {
            'incident_location': scenario.get('incident_location'),
            'num_casualties': scenario.get('num_casualties'),
            'triage_counts': triage_counts,
            'casualties': scenario.get('casualties', []),  # Include for map
            'ambulance_config': scenario.get('ambulance_config', {}),
            'metadata': scenario.get('metadata', {})
        }
