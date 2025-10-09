#!/usr/bin/env python3
"""
CLI Interface for MCI Simulation - Step 1.7

Run mass casualty incident simulations from the command line.
"""

import argparse
import json
import sys
import os
from datetime import datetime
from typing import Dict, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator.environment.hospital_loader import load_hospitals
from simulator.environment.scenario_generator import ScenarioGenerator, calculate_region_bounds
from simulator.simulation_engine import SimulationEngine
from simulator.agents.baselines import (
    random_policy,
    nearest_hospital_policy,
    triage_priority_policy,
    trauma_matching_policy,
    load_balancing_policy
)


def get_policy_function(policy_name: str):
    """
    Get policy function by name.

    Args:
        policy_name: Name of policy ('random', 'nearest', 'triage', 'trauma', 'load_balancing')

    Returns:
        Policy function

    Raises:
        ValueError: If policy name is unknown
    """
    policies = {
        'random': random_policy,
        'nearest': nearest_hospital_policy,
        'triage': triage_priority_policy,
        'trauma': trauma_matching_policy,
        'load_balancing': load_balancing_policy
    }

    policy = policies.get(policy_name.lower())
    if policy is None:
        available = ', '.join(policies.keys())
        raise ValueError(f"Unknown policy '{policy_name}'. Available: {available}")

    return policy


def run_single_simulation(args, scenario_num: int = 1) -> Dict:
    """
    Run a single simulation and return results.

    Args:
        args: Command-line arguments
        scenario_num: Scenario number for identification

    Returns:
        Results dictionary
    """
    # Load hospitals
    print(f"Loading hospitals for region: {args.region}...")
    hospitals = load_hospitals(region=args.region)

    if not hospitals:
        raise ValueError(f"No hospitals found for region '{args.region}'")

    print(f"  Loaded {len(hospitals)} hospitals")

    # Calculate region bounds
    region_bounds = calculate_region_bounds(hospitals)

    # Create scenario generator
    seed = args.seed + scenario_num if args.seed is not None else None
    generator = ScenarioGenerator(hospitals, region_bounds, seed=seed)

    # Generate scenario
    print(f"\nGenerating scenario {scenario_num}...")
    scenario = generator.generate_scenario(
        num_casualties=args.casualties,
        ambulances_per_hospital=args.ambulances_per_hospital,
        ambulances_per_hospital_variation=args.ambulance_variation,
        field_ambulances=args.field_ambulances,
        field_ambulance_radius_km=args.field_radius,
        seed=seed
    )

    print(f"  Casualties: {scenario['num_casualties']}")
    print(f"  Ambulance config: {args.ambulances_per_hospital}±{args.ambulance_variation} per hospital + {args.field_ambulances} field units")

    # Get policy
    policy = get_policy_function(args.policy)
    print(f"  Policy: {args.policy}")

    # Run simulation
    print(f"\nRunning simulation (max {args.max_time} minutes)...")
    engine = SimulationEngine(scenario, policy)
    engine.run(max_time_minutes=args.max_time)

    # Get results
    metrics = engine.get_metrics()
    print(f"\nSimulation {scenario_num} completed:")
    print(f"  Simulation time: {engine.current_time} minutes")
    print(f"  Deaths: {metrics['deaths']}")
    print(f"  Transported: {metrics['transported']}")
    print(f"  Average response time: {metrics['avg_response_time']:.2f} minutes")
    print(f"  Casualties waiting: {metrics['casualties_waiting']}")

    # Compile results
    results = {
        'scenario_num': scenario_num,
        'timestamp': datetime.now().isoformat(),
        'configuration': {
            'region': args.region,
            'num_casualties': args.casualties,
            'ambulances_per_hospital': args.ambulances_per_hospital,
            'ambulance_variation': args.ambulance_variation,
            'field_ambulances': args.field_ambulances,
            'field_radius_km': args.field_radius,
            'policy': args.policy,
            'max_time': args.max_time,
            'seed': seed
        },
        'scenario': {
            'incident_location': scenario['incident_location'],
            'num_hospitals': len(hospitals),
            'total_ambulances': len(engine.ambulances),
            'hospital_based_ambulances': sum(1 for a in engine.ambulances if a['type'] == 'HOSPITAL_BASED'),
            'field_unit_ambulances': sum(1 for a in engine.ambulances if a['type'] == 'FIELD_UNIT')
        },
        'metrics': metrics,
        'simulation_time': engine.current_time,
        'event_count': len(engine.event_log)
    }

    if args.include_events:
        results['events'] = engine.event_log

    return results


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Run MCI response simulations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic simulation
  python simulator/run_simulation.py --region CA --casualties 60 --policy random

  # With custom ambulance configuration
  python simulator/run_simulation.py --region CA --casualties 60 \\
      --ambulances-per-hospital 2 --ambulance-variation 1 \\
      --field-ambulances 5 --policy triage

  # Run multiple scenarios and save results
  python simulator/run_simulation.py --region CA --casualties 60 \\
      --policy load_balancing --num-scenarios 10 --output results.json

  # Include detailed event log
  python simulator/run_simulation.py --region CA --casualties 30 \\
      --policy trauma --include-events --output detailed_results.json

Available policies:
  random           - Random dispatch (baseline)
  nearest          - Nearest hospital (greedy)
  triage           - Triage priority (RED > YELLOW > GREEN)
  trauma           - Trauma center matching
  load_balancing   - Load balancing across hospitals
        """
    )

    # Required arguments
    parser.add_argument('--region', type=str, required=True,
                        help='State abbreviation (e.g., CA, NY, TX)')
    parser.add_argument('--casualties', type=int, required=True,
                        help='Number of casualties (50-80 recommended)')
    parser.add_argument('--policy', type=str, required=True,
                        help='Dispatch policy to use')

    # Ambulance configuration
    parser.add_argument('--ambulances-per-hospital', type=int, default=2,
                        help='Base number of ambulances per hospital (default: 2)')
    parser.add_argument('--ambulance-variation', type=int, default=1,
                        help='Random variation (+/-) in ambulances per hospital (default: 1)')
    parser.add_argument('--field-ambulances', type=int, default=3,
                        help='Number of field ambulances near incident (default: 3)')
    parser.add_argument('--field-radius', type=float, default=10.0,
                        help='Radius in km for field ambulance placement (default: 10.0)')

    # Simulation parameters
    parser.add_argument('--max-time', type=int, default=180,
                        help='Maximum simulation time in minutes (default: 180)')
    parser.add_argument('--num-scenarios', type=int, default=1,
                        help='Number of scenarios to run (default: 1)')
    parser.add_argument('--seed', type=int, default=None,
                        help='Random seed for reproducibility (default: None)')

    # Output options
    parser.add_argument('--output', type=str, default=None,
                        help='Output JSON file (default: print to console)')
    parser.add_argument('--include-events', action='store_true',
                        help='Include detailed event log in output')
    parser.add_argument('--verbose', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    # Validate arguments
    if args.casualties < 1:
        parser.error("--casualties must be positive")
    if args.num_scenarios < 1:
        parser.error("--num-scenarios must be positive")

    try:
        # Run simulations
        all_results = []

        for scenario_num in range(1, args.num_scenarios + 1):
            if args.num_scenarios > 1:
                print("\n" + "=" * 60)
                print(f"SCENARIO {scenario_num}/{args.num_scenarios}")
                print("=" * 60)

            results = run_single_simulation(args, scenario_num)
            all_results.append(results)

        # Summary for multiple scenarios
        if args.num_scenarios > 1:
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)

            avg_deaths = sum(r['metrics']['deaths'] for r in all_results) / len(all_results)
            avg_transported = sum(r['metrics']['transported'] for r in all_results) / len(all_results)
            avg_response_time = sum(r['metrics']['avg_response_time'] for r in all_results) / len(all_results)

            print(f"Average deaths: {avg_deaths:.2f}")
            print(f"Average transported: {avg_transported:.2f}")
            print(f"Average response time: {avg_response_time:.2f} minutes")

        # Save results
        if args.output:
            output_data = {
                'num_scenarios': args.num_scenarios,
                'results': all_results
            }

            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2)

            print(f"\n✓ Results saved to {args.output}")
        else:
            # Print results to console
            if not args.verbose:
                print("\n✓ Simulation(s) completed successfully")
                print("  (Use --output to save results to file)")

    except KeyboardInterrupt:
        print("\n\nSimulation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
