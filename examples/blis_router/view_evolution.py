#!/usr/bin/env python3
"""
View evolution history: all mutations and their scores.

Usage:
    python view_evolution.py                                    # Show all programs
    python view_evolution.py --top 10                          # Show top 10
    python view_evolution.py --checkpoint checkpoints/checkpoint_25
"""

import argparse
import pickle
from pathlib import Path
from typing import List, Dict


def load_database(checkpoint_path: str = None):
    """Load database from checkpoint or default location."""
    if checkpoint_path:
        db_path = Path(checkpoint_path) / "database.pkl"
    else:
        # Find most recent checkpoint
        output_dir = Path("openevolve_output/checkpoints")
        if not output_dir.exists():
            print("❌ No checkpoints found. Run evolution first.")
            return None

        checkpoints = sorted(output_dir.glob("checkpoint_*"))
        if not checkpoints:
            print("❌ No checkpoints found. Run evolution first.")
            return None

        db_path = checkpoints[-1] / "database.pkl"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return None

    with open(db_path, "rb") as f:
        return pickle.load(f)


def format_score(score: float) -> str:
    """Format score with color based on value."""
    if score > -2000:
        return f"\033[92m{score:8.2f}\033[0m"  # Green (good)
    elif score > -2100:
        return f"\033[93m{score:8.2f}\033[0m"  # Yellow (ok)
    else:
        return f"\033[91m{score:8.2f}\033[0m"  # Red (bad)


def print_program_table(programs: List, title: str):
    """Print programs in a clean table format."""
    print()
    print("=" * 100)
    print(f"{title}")
    print("=" * 100)
    print(f"{'Iter':<6} {'Gen':<5} {'Score':<10} {'Light':<10} {'Heavy':<10} {'Mixed':<10} {'Island':<8} {'ID':<12}")
    print("-" * 100)

    for prog in programs:
        iteration = prog.iteration_found if hasattr(prog, 'iteration_found') else prog.metadata.get('iteration_found', '?')
        generation = prog.generation
        score = prog.metrics.get('combined_score', 0.0)
        light = prog.metrics.get('light_e2e_ms', 0.0)
        heavy = prog.metrics.get('heavy_e2e_ms', 0.0)
        mixed = prog.metrics.get('mixed_e2e_ms', 0.0)
        island = prog.metadata.get('island', 0)
        prog_id = prog.id[:8]

        print(f"{iteration:<6} {generation:<5} {format_score(score)} "
              f"{light:8.1f}ms {heavy:8.1f}ms {mixed:8.1f}ms "
              f"{island:<8} {prog_id:<12}")

    print("=" * 100)
    print()


def show_stats(database):
    """Show database statistics."""
    all_programs = database.get_all_programs()

    print()
    print("=" * 100)
    print("DATABASE STATISTICS")
    print("=" * 100)
    print(f"Total programs: {len(all_programs)}")
    print(f"Islands: {database.num_islands}")
    print(f"Generations: {max(p.generation for p in all_programs) if all_programs else 0}")

    if all_programs:
        scores = [p.metrics.get('combined_score', 0.0) for p in all_programs]
        print(f"Best score: {format_score(max(scores))}")
        print(f"Worst score: {format_score(min(scores))}")
        print(f"Average score: {format_score(sum(scores) / len(scores))}")

    print("=" * 100)


def main():
    parser = argparse.ArgumentParser(description="View evolution history")
    parser.add_argument("--checkpoint", help="Path to checkpoint directory")
    parser.add_argument("--top", type=int, help="Show only top N programs")
    parser.add_argument("--all", action="store_true", help="Show all programs (sorted by score)")
    parser.add_argument("--by-iteration", action="store_true", help="Show programs by iteration")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")

    args = parser.parse_args()

    # Load database
    database = load_database(args.checkpoint)
    if database is None:
        return

    # Show stats
    if args.stats:
        show_stats(database)
        return

    # Get programs
    all_programs = database.get_all_programs()

    if not all_programs:
        print("❌ No programs in database")
        return

    # Sort and filter
    if args.by_iteration:
        # Sort by iteration
        programs = sorted(all_programs, key=lambda p: p.iteration_found if hasattr(p, 'iteration_found') else 0)
        print_program_table(programs, "ALL PROGRAMS (by iteration)")
    elif args.top:
        # Show top N
        programs = sorted(all_programs, key=lambda p: p.metrics.get('combined_score', 0.0), reverse=True)[:args.top]
        print_program_table(programs, f"TOP {args.top} PROGRAMS")
    elif args.all:
        # Show all, sorted by score
        programs = sorted(all_programs, key=lambda p: p.metrics.get('combined_score', 0.0), reverse=True)
        print_program_table(programs, "ALL PROGRAMS (by score)")
    else:
        # Default: show stats + top 10
        show_stats(database)
        programs = sorted(all_programs, key=lambda p: p.metrics.get('combined_score', 0.0), reverse=True)[:10]
        print_program_table(programs, "TOP 10 PROGRAMS")
        print(f"💡 Use --all to see all {len(all_programs)} programs")
        print(f"💡 Use --by-iteration to sort by iteration")
        print(f"💡 Use --top N to show top N programs")


if __name__ == "__main__":
    main()
