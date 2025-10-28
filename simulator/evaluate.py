#!/usr/bin/env python3
"""
Evaluation Script for Trained Models - Step 2.4

Evaluate trained PPO agents and baseline policies on test scenarios.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
from stable_baselines3 import PPO
from simulator.environment.mci_env import MCIResponseEnv
from simulator.agents.baselines import (
    random_policy,
    nearest_hospital_policy,
    triage_priority_policy,
    trauma_matching_policy,
    load_balancing_policy,
)


def evaluate_ppo_model(
    model_path: str, env: MCIResponseEnv, num_episodes: int, device: str = "cuda"
) -> List[Dict]:
    """Evaluate PPO model on environment"""
    print(f"Loading PPO model from {model_path}...")
    load_start = time.time()
    model = PPO.load(model_path, device=device)
    load_time = time.time() - load_start
    print(f"✓ Model loaded in {load_time:.2f}s (device: {device})")
    print("Evaluating PPO model...")

    results = []
    total_steps = 0
    total_inference_time = 0
    total_episode_time = 0

    for episode in range(num_episodes):
        episode_start = time.time()

        obs, info = env.reset()
        episode_reward = 0
        done = False
        truncated = False
        step_count = 0

        print(f"\n  Episode {episode + 1}/{num_episodes}:")
        print(f"    Scenario: {info.get('num_casualties', 'N/A')} casualties, "
              f"{info.get('num_ambulances', 'N/A')} ambulances, "
              f"{info.get('num_hospitals', 'N/A')} hospitals")

        while not (done or truncated):
            # Time model inference
            inference_start = time.time()
            action, _states = model.predict(obs, deterministic=True)
            inference_time = time.time() - inference_start
            total_inference_time += inference_time

            # Time environment step
            step_start = time.time()
            obs, reward, done, truncated, info = env.step(action)
            step_time = time.time() - step_start

            episode_reward += reward
            step_count += 1

            # Progress indicator every 30 steps
            if step_count % 30 == 0:
                sim_time = info.get('current_time', step_count)
                metrics = info.get('metrics', {})
                casualties_waiting = metrics.get('casualties_waiting', 0)
                deaths = metrics.get('deaths', 0)

                # Warning for slow operations
                warning = ""
                if inference_time > 0.5:  # > 500ms
                    warning = " [SLOW INFERENCE]"
                elif step_time > 1.0:  # > 1000ms
                    warning = " [SLOW STEP]"

                print(f"    Step {step_count:3d} | Sim time: {sim_time:3d}min | "
                      f"Waiting: {casualties_waiting:2d} | Deaths: {deaths:2d} | "
                      f"Inference: {inference_time*1000:.1f}ms | Step: {step_time*1000:.1f}ms{warning}")

        episode_time = time.time() - episode_start
        total_episode_time += episode_time
        total_steps += step_count

        metrics = info["metrics"]
        results.append(
            {
                "episode": episode + 1,
                "reward": float(episode_reward),
                "deaths": metrics["deaths"],
                "transported": metrics["transported"],
                "avg_response_time": metrics["avg_response_time"],
                "casualties_waiting": metrics["casualties_waiting"],
                "num_steps": step_count,
                "episode_time_sec": episode_time,
            }
        )

        print(f"    ✓ Episode {episode + 1} completed in {episode_time:.2f}s ({step_count} steps)")
        print(f"      Deaths: {metrics['deaths']}, Transported: {metrics['transported']}, Reward: {episode_reward:.1f}")
        print(f"      Avg time per step: {episode_time/step_count*1000:.1f}ms "
              f"(inference: {total_inference_time/step_count*1000:.1f}ms)")

    # Summary statistics
    print(f"\n{'=' * 70}")
    print("Performance Summary:")
    print(f"  Total episodes: {num_episodes}")
    print(f"  Total steps: {total_steps}")
    print(f"  Avg steps per episode: {total_steps/num_episodes:.1f}")
    print(f"  Total time: {total_episode_time:.2f}s")
    print(f"  Avg time per episode: {total_episode_time/num_episodes:.2f}s")
    print(f"  Avg time per step: {total_episode_time/total_steps*1000:.1f}ms")
    print(f"  Model inference time: {total_inference_time:.2f}s ({total_inference_time/total_episode_time*100:.1f}% of total)")
    print(f"  Avg inference per step: {total_inference_time/total_steps*1000:.1f}ms")
    print("=" * 70)

    return results


def evaluate_baseline_policy(
    policy_func, policy_name: str, env: MCIResponseEnv, num_episodes: int
) -> List[Dict]:
    """Evaluate baseline policy through simulation engine"""
    from simulator.environment.hospital_loader import load_hospitals
    from simulator.environment.scenario_generator import (
        ScenarioGenerator,
        calculate_region_bounds,
    )
    from simulator.simulation_engine import SimulationEngine

    print(f"Evaluating {policy_name} policy...")

    hospitals = load_hospitals(region=env.region)
    if len(hospitals) > env.max_hospitals:
        hospitals = hospitals[: env.max_hospitals]

    region_bounds = calculate_region_bounds(hospitals)
    generator = ScenarioGenerator(hospitals, region_bounds)

    results = []
    total_episode_time = 0

    for episode in range(num_episodes):
        episode_start = time.time()

        num_casualties = np.random.randint(
            env.num_casualties_range[0], env.num_casualties_range[1] + 1
        )

        scenario = generator.generate_scenario(
            num_casualties=num_casualties,
            ambulances_per_hospital=2,
            ambulances_per_hospital_variation=1,
            field_ambulances=5,
            field_ambulance_radius_km=10.0,
            seed=episode,
        )

        print(f"\n  Episode {episode + 1}/{num_episodes}:")
        print(f"    Scenario: {num_casualties} casualties, "
              f"{len(scenario['ambulances'])} ambulances, "
              f"{len(scenario['hospitals'])} hospitals")

        engine = SimulationEngine(scenario, policy_func)
        engine.run(max_time_minutes=env.max_time_minutes)

        episode_time = time.time() - episode_start
        total_episode_time += episode_time

        metrics = engine.get_metrics()
        results.append(
            {
                "episode": episode + 1,
                "reward": 0.0,  # Baselines don't have reward
                "deaths": metrics["deaths"],
                "transported": metrics["transported"],
                "avg_response_time": metrics["avg_response_time"],
                "casualties_waiting": metrics["casualties_waiting"],
                "episode_time_sec": episode_time,
            }
        )

        print(f"    ✓ Episode {episode + 1} completed in {episode_time:.2f}s")
        print(f"      Deaths: {metrics['deaths']}, Transported: {metrics['transported']}")

    # Summary statistics
    print(f"\n{'=' * 70}")
    print(f"{policy_name.upper()} Performance Summary:")
    print(f"  Total episodes: {num_episodes}")
    print(f"  Total time: {total_episode_time:.2f}s")
    print(f"  Avg time per episode: {total_episode_time/num_episodes:.2f}s")
    print("=" * 70)

    return results


def calculate_statistics(results: List[Dict]) -> Dict:
    """Calculate summary statistics from results"""
    deaths = [r["deaths"] for r in results]
    transported = [r["transported"] for r in results]
    response_times = [r["avg_response_time"] for r in results]

    return {
        "num_episodes": len(results),
        "deaths": {
            "mean": float(np.mean(deaths)),
            "std": float(np.std(deaths)),
            "min": int(np.min(deaths)),
            "max": int(np.max(deaths)),
        },
        "transported": {
            "mean": float(np.mean(transported)),
            "std": float(np.std(transported)),
            "min": int(np.min(transported)),
            "max": int(np.max(transported)),
        },
        "avg_response_time": {
            "mean": float(np.mean(response_times)),
            "std": float(np.std(response_times)),
            "min": float(np.min(response_times)),
            "max": float(np.max(response_times)),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate trained PPO model and baseline policies",
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
        """,
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Path to trained PPO model (default: None)",
    )
    parser.add_argument(
        "--baselines",
        nargs="+",
        default=[],
        help="Baseline policies to evaluate: random, nearest, triage, trauma, load_balancing, all",
    )
    parser.add_argument(
        "--num-scenarios",
        type=int,
        default=100,
        help="Number of test scenarios (default: 100)",
    )

    # Environment parameters (must match training)
    parser.add_argument(
        "--region", type=str, default="CA", help="Region for hospitals (default: CA)"
    )
    parser.add_argument(
        "--max-hospitals",
        type=int,
        default=50,
        help="Max hospitals (must match training, default: 50)",
    )
    parser.add_argument(
        "--max-ambulances",
        type=int,
        default=100,
        help="Max ambulances (must match training, default: 100)",
    )
    parser.add_argument(
        "--max-casualties",
        type=int,
        default=80,
        help="Max casualties (must match training, default: 80)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file for results (default: None)",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed (default: 42)"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        help="Device to use for model inference: cuda, cpu (default: cuda)",
    )

    args = parser.parse_args()

    if not args.model and not args.baselines:
        parser.error("Must specify --model and/or --baselines")

    np.random.seed(args.seed)

    # Check CUDA availability
    if args.device == "cuda" and not torch.cuda.is_available():
        print(f"\n⚠ WARNING: CUDA requested but not available. Falling back to CPU.")
        print(f"  This will be significantly slower for model inference.")
        args.device = "cpu"

    print("=" * 70)
    print("MCI Response Model Evaluation")
    print("=" * 70)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Test scenarios: {args.num_scenarios}")
    print(f"Region: {args.region}")
    print(f"Random seed: {args.seed}")
    print(f"Device: {args.device}")
    if args.device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    # Create environment
    env = MCIResponseEnv(
        region=args.region,
        max_hospitals=args.max_hospitals,
        max_ambulances=args.max_ambulances,
        max_casualties=args.max_casualties,
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

        ppo_results = evaluate_ppo_model(args.model, env, args.num_scenarios, args.device)
        ppo_stats = calculate_statistics(ppo_results)
        all_results["ppo"] = {
            "model_path": args.model,
            "statistics": ppo_stats,
            "episodes": ppo_results,
        }

        print(f"\nPPO Statistics:")
        print(
            f"  Deaths: {ppo_stats['deaths']['mean']:.2f} ± {ppo_stats['deaths']['std']:.2f}"
        )
        print(
            f"  Transported: {ppo_stats['transported']['mean']:.2f} ± {ppo_stats['transported']['std']:.2f}"
        )
        print(
            f"  Avg Response Time: {ppo_stats['avg_response_time']['mean']:.2f} ± {ppo_stats['avg_response_time']['std']:.2f} min"
        )

    # Evaluate baselines
    baseline_policies = {
        "random": random_policy,
        "nearest": nearest_hospital_policy,
        "triage": triage_priority_policy,
        "trauma": trauma_matching_policy,
        "load_balancing": load_balancing_policy,
    }

    if "all" in args.baselines:
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
            baseline_policies[baseline_name], baseline_name, env, args.num_scenarios
        )
        baseline_stats = calculate_statistics(baseline_results)
        all_results[baseline_name] = {
            "statistics": baseline_stats,
            "episodes": baseline_results,
        }

        print(f"\n{baseline_name.upper()} Statistics:")
        print(
            f"  Deaths: {baseline_stats['deaths']['mean']:.2f} ± {baseline_stats['deaths']['std']:.2f}"
        )
        print(
            f"  Transported: {baseline_stats['transported']['mean']:.2f} ± {baseline_stats['transported']['std']:.2f}"
        )
        print(
            f"  Avg Response Time: {baseline_stats['avg_response_time']['mean']:.2f} ± {baseline_stats['avg_response_time']['std']:.2f} min"
        )

    # Comparison summary
    if len(all_results) > 1:
        print(f"\n{'=' * 70}")
        print("Comparison Summary")
        print("=" * 70)
        print(
            f"\n{'Policy':<20} {'Deaths':<15} {'Transported':<15} {'Response Time':<15}"
        )
        print("-" * 70)

        for policy_name, data in all_results.items():
            stats = data["statistics"]
            print(
                f"{policy_name.upper():<20} "
                f"{stats['deaths']['mean']:>6.2f} ± {stats['deaths']['std']:<5.2f} "
                f"{stats['transported']['mean']:>6.2f} ± {stats['transported']['std']:<5.2f} "
                f"{stats['avg_response_time']['mean']:>6.2f} ± {stats['avg_response_time']['std']:<5.2f}"
            )

        # Calculate improvement if PPO exists
        if "ppo" in all_results and baselines_to_eval:
            ppo_deaths = all_results["ppo"]["statistics"]["deaths"]["mean"]

            print(f"\n{'=' * 70}")
            print("PPO Improvement vs Baselines")
            print("=" * 70)

            for baseline_name in baselines_to_eval:
                if baseline_name in all_results:
                    baseline_deaths = all_results[baseline_name]["statistics"][
                        "deaths"
                    ]["mean"]
                    improvement = (
                        (baseline_deaths - ppo_deaths) / baseline_deaths
                    ) * 100
                    print(
                        f"  vs {baseline_name.upper()}: {improvement:+.2f}% mortality reduction"
                    )

    # Save results
    if args.output:
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "configuration": {
                "num_scenarios": args.num_scenarios,
                "region": args.region,
                "max_hospitals": args.max_hospitals,
                "max_ambulances": args.max_ambulances,
                "max_casualties": args.max_casualties,
                "seed": args.seed,
            },
            "results": all_results,
        }

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)

        print(f"\n✓ Results saved to {args.output}")

    print("\n" + "=" * 70)
    print("Evaluation completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
