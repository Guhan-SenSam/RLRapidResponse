#!/usr/bin/env python3
"""
Unified CLI for MCI Response System

Provides commands for simulation, training, and evaluation.
"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        description='MCI Response System - Ambulance Dispatch Optimization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  simulate    Run simulations with baseline policies or trained models
  train       Train a PPO agent
  evaluate    Evaluate trained models and baseline policies

Examples:
  # Run simulation with baseline policy
  python mci_cli.py simulate --scenario-file scenarios/benchmark/tampa_1.json --policy nearest

  # Train a PPO model
  python mci_cli.py train --timesteps 1000000 --output models/ppo_mci

  # Evaluate trained model
  python mci_cli.py evaluate --model models/ppo_mci.zip --num-scenarios 100

For detailed help on each command:
  python mci_cli.py simulate --help
  python mci_cli.py train --help
  python mci_cli.py evaluate --help
        """
    )

    parser.add_argument('command', choices=['simulate', 'train', 'evaluate'],
                        help='Command to run')
    parser.add_argument('args', nargs=argparse.REMAINDER,
                        help='Arguments for the command')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # Dispatch to appropriate module
    if args.command == 'simulate':
        from simulator import run_simulation
        sys.argv = ['run_simulation.py'] + args.args
        run_simulation.main()

    elif args.command == 'train':
        from simulator import train
        sys.argv = ['train.py'] + args.args
        train.main()

    elif args.command == 'evaluate':
        from simulator import evaluate
        sys.argv = ['evaluate.py'] + args.args
        evaluate.main()


if __name__ == '__main__':
    main()
