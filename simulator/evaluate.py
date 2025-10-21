#!/usr/bin/env python3
"""
Evaluation Script for Trained Models - Step 2.4

Evaluate trained PPO agents and baseline policies on test scenarios.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stable_baselines3 import PPO
from simulator.environment.mci_env import MCIResponseEnv
from simulator.agents.baselines import (
    random_policy,
    nearest_hospital_policy,
    triage_priority_policy,
    trauma_matching_policy,
    load_balancing_policy
)


def evaluate_ppo_model(model_path: str, env: MCIResponseEnv, num_episodes: int) -> List[Dict]:
    """Evaluate PPO model on environment"""
    print(f"Loading PPO model from {model_path}...")
    model = PPO.load(model_path)

    results = []
    for episode in range(num_episodes):
        obs, info = env.reset()
        episode_reward = 0
        done = False
        truncated = False

        while not (done or truncated):
            action, _states = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step(action)
            episode_reward += reward

        metrics = info['metrics']
        results.append({
            'episode': episode + 1,
            'reward': float(episode_reward),
            'deaths': metrics['deaths'],
            'transported': metrics['transported'],
            'avg_response_time': metrics['avg_response_time'],
            'casualties_waiting': metrics['casualties_waiting']
        })

        print(f"  Episode {episode + 1}/{num_episodes}: "
              f"Deaths={metrics['deaths']}, "
              f"Transported={metrics['transported']}, "
              f"Reward={episode_reward:.1f}")

    return results


def evaluate_baseline_policy(policy_func, policy_name: str, env: MCIResponseEnv, num_episodes: int) -> List[Dict]:
    """Evaluate baseline policy through simulation engine"""
    from simulator.environment.hospital_loader import load_hospitals
    from simulator.environment.scenario_generator import ScenarioGenerator, calculate_region_bounds
    from simulator.simulation_engine import SimulationEngine

    print(f"Evaluating {policy_name} policy...")

    hospitals = load_hospitals(region=env.region)
    if len(hospitals) > env.max_hospitals:
        hospitals = hospitals[:env.max_hospitals]

    region_bounds = calculate_region_bounds(hospitals)
    generator = ScenarioGenerator(hospitals, region_bounds)

    results = []
    for episode in range(num_episodes):
        num_casualties = np.random.randint(
            env.num_casualties_range[0],
            env.num_casualties_range[1] + 1
        )

        scenario = generator.generate_scenario(
            num_casualties=num_casualties,
            ambulances_per_hospital=2,
            ambulances_per_hospital_variation=1,
            field_ambulances=5,
            field_ambulance_radius_km=10.0,
            seed=episode
        )

        engine = SimulationEngine(scenario, policy_func)
        engine.run(max_time_minutes=env.max_time_minutes)

        metrics = engine.get_metrics()
        results.append({
            'episode': episode + 1,
            'reward': 0.0,  # Baselines don't have reward
            'deaths': metrics['deaths'],
            'transported': metrics['transported'],
            'avg_response_time': metrics['avg_response_time'],
            'casualties_waiting': metrics['casualties_waiting']
        })

        print(f"  Episode {episode + 1}/{num_episodes}: "
              f"Deaths={metrics['deaths']}, "
              f"Transported={metrics['transported']}")

    return results


def calculate_statistics(results: List[Dict]) -> Dict:
    """Calculate summary statistics from results"""
    deaths = [r['deaths'] for r in results]
    transported = [r['transported'] for r in results]
    response_times = [r['avg_response_time'] for r in results]

    return {
        'num_episodes': len(results),
        'deaths': {
            'mean': float(np.mean(deaths)),
            'std': float(np.std(deaths)),
            'min': int(np.min(deaths)),
            'max': int(np.max(deaths))
        },
        'transported': {
            'mean': float(np.mean(transported)),
            'std': float(np.std(transported)),
            'min': int(np.min(transported)),
            'max': int(np.max(transported))
        },
        'avg_response_time': {
            'mean': float(np.mean(response_times)),
            'std': float(np.std(response_times)),
            'min': float(np.min(response_times)),
            'max': float(np.max(response_times))
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description='Evaluate trained PPO model and baseline policies',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate trained model
  python simulator/evaluate.py --model models/ppo_mci.zip --num-scenarios 100

  # Compare model against specific baselines
  python simulator/evaluate.py --model models/ppo_mci.zip --baselines nearest triage --num-scenarios 50

  # Evaluate all baselines (no model)
  python simulator/evaluate.py --baselines all --num-scenarios 100 --output baseline_comparison.json

  # Full comparison with output
  python simulator/evaluate.py --model models/ppo_mci.zip --baselines all --num-scenarios 100 --output evaluation.json
        """
    )

    parser.add_argument('--model', type=str, default=None,
                        help='Path to trained PPO model (default: None)')
    parser.add_argument('--baselines', nargs='+', default=[],
                        help='Baseline policies to evaluate: random, nearest, triage, trauma, load_balancing, all')
    parser.add_argument('--num-scenarios', type=int, default=100,
                        help='Number of test scenarios (default: 100)')

    # Environment parameters (must match training)
    parser.add_argument('--region', type=str, default='CA',
                        help='Region for hospitals (default: CA)')
    parser.add_argument('--max-hospitals', type=int, default=50,
                        help='Max hospitals (must match training, default: 50)')
    parser.add_argument('--max-ambulances', type=int, default=100,
                        help='Max ambulances (must match training, default: 100)')
    parser.add_argument('--max-casualties', type=int, default=80,
                        help='Max casualties (must match training, default: 80)')

    parser.add_argument('--output', type=str, default=None,
                        help='Output JSON file for results (default: None)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed (default: 42)')

    args = parser.parse_args()

    if not args.model and not args.baselines:
        parser.error("Must specify --model and/or --baselines")

    np.random.seed(args.seed)

    print("=" * 70)
    print("MCI Response Model Evaluation")
    print("=" * 70)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Test scenarios: {args.num_scenarios}")
    print(f"Region: {args.region}")
    print(f"Random seed: {args.seed}")

    # Create environment
    env = MCIResponseEnv(
        region=args.region,
        max_hospitals=args.max_hospitals,
        max_ambulances=args.max_ambulances,
        max_casualties=args.max_casualties
    )

    all_results = {}

    # Evaluate PPO model
    if args.model:
        print(f"\n{'=' * 70}")
        print("Evaluating PPO Model")
        print("=" * 70)

        if not os.path.exists(args.model):
            print(f"✗ Model file not found: {args.model}")
            sys.exit(1)

        ppo_results = evaluate_ppo_model(args.model, env, args.num_scenarios)
        ppo_stats = calculate_statistics(ppo_results)
        all_results['ppo'] = {
            'model_path': args.model,
            'statistics': ppo_stats,
            'episodes': ppo_results
        }

        print(f"\nPPO Statistics:")
        print(f"  Deaths: {ppo_stats['deaths']['mean']:.2f} ± {ppo_stats['deaths']['std']:.2f}")
        print(f"  Transported: {ppo_stats['transported']['mean']:.2f} ± {ppo_stats['transported']['std']:.2f}")
        print(f"  Avg Response Time: {ppo_stats['avg_response_time']['mean']:.2f} ± {ppo_stats['avg_response_time']['std']:.2f} min")

    # Evaluate baselines
    baseline_policies = {
        'random': random_policy,
        'nearest': nearest_hospital_policy,
        'triage': triage_priority_policy,
        'trauma': trauma_matching_policy,
        'load_balancing': load_balancing_policy
    }

    if 'all' in args.baselines:
        baselines_to_eval = list(baseline_policies.keys())
    else:
        baselines_to_eval = args.baselines

    for baseline_name in baselines_to_eval:
        if baseline_name not in baseline_policies:
            print(f"✗ Unknown baseline: {baseline_name}")
            continue

        print(f"\n{'=' * 70}")
        print(f"Evaluating {baseline_name.upper()} Policy")
        print("=" * 70)

        baseline_results = evaluate_baseline_policy(
            baseline_policies[baseline_name],
            baseline_name,
            env,
            args.num_scenarios
        )
        baseline_stats = calculate_statistics(baseline_results)
        all_results[baseline_name] = {
            'statistics': baseline_stats,
            'episodes': baseline_results
        }

        print(f"\n{baseline_name.upper()} Statistics:")
        print(f"  Deaths: {baseline_stats['deaths']['mean']:.2f} ± {baseline_stats['deaths']['std']:.2f}")
        print(f"  Transported: {baseline_stats['transported']['mean']:.2f} ± {baseline_stats['transported']['std']:.2f}")
        print(f"  Avg Response Time: {baseline_stats['avg_response_time']['mean']:.2f} ± {baseline_stats['avg_response_time']['std']:.2f} min")

    # Comparison summary
    if len(all_results) > 1:
        print(f"\n{'=' * 70}")
        print("Comparison Summary")
        print("=" * 70)
        print(f"\n{'Policy':<20} {'Deaths':<15} {'Transported':<15} {'Response Time':<15}")
        print("-" * 70)

        for policy_name, data in all_results.items():
            stats = data['statistics']
            print(f"{policy_name.upper():<20} "
                  f"{stats['deaths']['mean']:>6.2f} ± {stats['deaths']['std']:<5.2f} "
                  f"{stats['transported']['mean']:>6.2f} ± {stats['transported']['std']:<5.2f} "
                  f"{stats['avg_response_time']['mean']:>6.2f} ± {stats['avg_response_time']['std']:<5.2f}")

        # Calculate improvement if PPO exists
        if 'ppo' in all_results and baselines_to_eval:
            ppo_deaths = all_results['ppo']['statistics']['deaths']['mean']

            print(f"\n{'=' * 70}")
            print("PPO Improvement vs Baselines")
            print("=" * 70)

            for baseline_name in baselines_to_eval:
                if baseline_name in all_results:
                    baseline_deaths = all_results[baseline_name]['statistics']['deaths']['mean']
                    improvement = ((baseline_deaths - ppo_deaths) / baseline_deaths) * 100
                    print(f"  vs {baseline_name.upper()}: {improvement:+.2f}% mortality reduction")

    # Save results
    if args.output:
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'configuration': {
                'num_scenarios': args.num_scenarios,
                'region': args.region,
                'max_hospitals': args.max_hospitals,
                'max_ambulances': args.max_ambulances,
                'max_casualties': args.max_casualties,
                'seed': args.seed
            },
            'results': all_results
        }

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"\n✓ Results saved to {args.output}")

    print("\n" + "=" * 70)
    print("Evaluation completed!")
    print("=" * 70)


if __name__ == '__main__':
    main()
