#!/usr/bin/env python3
"""
Training Script for PPO Agent - Step 2.3

Train a PPO agent to optimize ambulance dispatch during mass casualty incidents.
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
from simulator.environment.mci_env import MCIResponseEnv


def create_env(region='CA', max_hospitals=50, max_ambulances=100, max_casualties=80, **kwargs):
    """Create and wrap environment"""
    env = MCIResponseEnv(
        region=region,
        max_hospitals=max_hospitals,
        max_ambulances=max_ambulances,
        max_casualties=max_casualties,
        **kwargs
    )
    return Monitor(env)


def main():
    parser = argparse.ArgumentParser(
        description='Train PPO agent for MCI response',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick training test (100k steps)
  python simulator/train.py --timesteps 100000 --output models/test_ppo

  # Full training run (1M steps)
  python simulator/train.py --timesteps 1000000 --output models/ppo_mci --n-envs 8

  # Training with custom hyperparameters
  python simulator/train.py --timesteps 500000 --learning-rate 0.0001 --batch-size 128

  # Resume training from checkpoint
  python simulator/train.py --timesteps 500000 --load models/ppo_mci.zip --output models/ppo_mci_continued
        """
    )

    parser.add_argument('--timesteps', type=int, default=100000,
                        help='Total timesteps to train (default: 100000)')
    parser.add_argument('--output', type=str, default='models/ppo_mci',
                        help='Output path for saved model (default: models/ppo_mci)')
    parser.add_argument('--load', type=str, default=None,
                        help='Load existing model to continue training (default: None)')

    # Environment parameters
    parser.add_argument('--region', type=str, default='CA',
                        help='Region for hospitals (default: CA)')
    parser.add_argument('--max-hospitals', type=int, default=50,
                        help='Max hospitals in environment (default: 50)')
    parser.add_argument('--max-ambulances', type=int, default=100,
                        help='Max ambulances in environment (default: 100)')
    parser.add_argument('--max-casualties', type=int, default=80,
                        help='Max casualties in environment (default: 80)')
    parser.add_argument('--n-envs', type=int, default=4,
                        help='Number of parallel environments (default: 4)')

    # PPO hyperparameters
    parser.add_argument('--learning-rate', type=float, default=3e-4,
                        help='Learning rate (default: 0.0003)')
    parser.add_argument('--batch-size', type=int, default=64,
                        help='Minibatch size (default: 64)')
    parser.add_argument('--n-steps', type=int, default=2048,
                        help='Steps per environment per update (default: 2048)')
    parser.add_argument('--n-epochs', type=int, default=10,
                        help='Number of epochs for policy update (default: 10)')
    parser.add_argument('--gamma', type=float, default=0.99,
                        help='Discount factor (default: 0.99)')
    parser.add_argument('--ent-coef', type=float, default=0.01,
                        help='Entropy coefficient (default: 0.01)')

    # Training options
    parser.add_argument('--device', type=str, default='auto',
                        help='Device to use: cpu, cuda, auto (default: auto)')
    parser.add_argument('--checkpoint-freq', type=int, default=50000,
                        help='Save checkpoint every N steps (default: 50000)')
    parser.add_argument('--eval-freq', type=int, default=10000,
                        help='Evaluate every N steps (default: 10000)')
    parser.add_argument('--n-eval-episodes', type=int, default=5,
                        help='Number of episodes for evaluation (default: 5)')
    parser.add_argument('--tensorboard-log', type=str, default='./logs/tensorboard',
                        help='TensorBoard log directory (default: ./logs/tensorboard)')
    parser.add_argument('--verbose', type=int, default=1,
                        help='Verbosity level: 0=none, 1=info, 2=debug (default: 1)')

    args = parser.parse_args()

    # Create output directories
    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_dir = output_dir / 'checkpoints'
    checkpoint_dir.mkdir(exist_ok=True)

    eval_dir = output_dir / 'eval_logs'
    eval_dir.mkdir(exist_ok=True)

    print("=" * 70)
    print("MCI Response PPO Training")
    print("=" * 70)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nConfiguration:")
    print(f"  Total timesteps: {args.timesteps:,}")
    print(f"  Parallel environments: {args.n_envs}")
    print(f"  Region: {args.region}")
    print(f"  Max hospitals: {args.max_hospitals}")
    print(f"  Max ambulances: {args.max_ambulances}")
    print(f"  Max casualties: {args.max_casualties}")
    print(f"\nHyperparameters:")
    print(f"  Learning rate: {args.learning_rate}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  N steps: {args.n_steps}")
    print(f"  N epochs: {args.n_epochs}")
    print(f"  Gamma: {args.gamma}")
    print(f"  Entropy coefficient: {args.ent_coef}")
    print(f"\nDevice: {args.device}")
    print(f"Output: {args.output}")
    print(f"TensorBoard logs: {args.tensorboard_log}")

    # Create vectorized training environment
    print("\nCreating training environments...")
    env = make_vec_env(
        lambda: create_env(
            region=args.region,
            max_hospitals=args.max_hospitals,
            max_ambulances=args.max_ambulances,
            max_casualties=args.max_casualties
        ),
        n_envs=args.n_envs
    )

    # Create evaluation environment
    print("Creating evaluation environment...")
    eval_env = make_vec_env(
        lambda: create_env(
            region=args.region,
            max_hospitals=args.max_hospitals,
            max_ambulances=args.max_ambulances,
            max_casualties=args.max_casualties
        ),
        n_envs=1
    )

    # Create or load model
    if args.load:
        print(f"\nLoading model from {args.load}...")
        model = PPO.load(
            args.load,
            env=env,
            device=args.device,
            tensorboard_log=args.tensorboard_log
        )
        print("Model loaded successfully")
    else:
        print("\nCreating new PPO model...")
        model = PPO(
            "MultiInputPolicy",
            env,
            learning_rate=args.learning_rate,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            n_epochs=args.n_epochs,
            gamma=args.gamma,
            ent_coef=args.ent_coef,
            verbose=args.verbose,
            device=args.device,
            tensorboard_log=args.tensorboard_log
        )

    # Setup callbacks
    checkpoint_callback = CheckpointCallback(
        save_freq=args.checkpoint_freq // args.n_envs,
        save_path=str(checkpoint_dir),
        name_prefix='ppo_mci_checkpoint',
        save_replay_buffer=False,
        save_vecnormalize=True
    )

    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=str(eval_dir),
        log_path=str(eval_dir),
        eval_freq=args.eval_freq // args.n_envs,
        n_eval_episodes=args.n_eval_episodes,
        deterministic=True,
        render=False
    )

    # Train
    print("\n" + "=" * 70)
    print("Starting training...")
    print("=" * 70)
    print(f"\nMonitor training progress:")
    print(f"  TensorBoard: tensorboard --logdir {args.tensorboard_log}")
    print(f"  Checkpoints: {checkpoint_dir}")
    print(f"  Eval logs: {eval_dir}")
    print()

    try:
        model.learn(
            total_timesteps=args.timesteps,
            callback=[checkpoint_callback, eval_callback],
            progress_bar=True
        )

        # Save final model
        print(f"\nSaving final model to {args.output}.zip...")
        model.save(args.output)

        print("\n" + "=" * 70)
        print("Training completed successfully!")
        print("=" * 70)
        print(f"\nFinal model saved: {args.output}.zip")
        print(f"Checkpoints saved: {checkpoint_dir}")
        print(f"Evaluation logs: {eval_dir}")
        print(f"\nTo evaluate the model:")
        print(f"  python simulator/evaluate.py --model {args.output}.zip --num-scenarios 100")

    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user")
        print(f"Saving current model to {args.output}_interrupted.zip...")
        model.save(f"{args.output}_interrupted")
        sys.exit(1)

    except Exception as e:
        print(f"\n✗ Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
