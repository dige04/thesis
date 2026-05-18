"""Example usage of SWE-Bench-CL dataset loader.

This example demonstrates how to load and inspect sequences from the
SWE-Bench-CL curriculum.
"""

from pathlib import Path

from src.benchmark import SWEBenchCLLoader


def main() -> None:
    """Load and display SWE-Bench-CL sequences."""
    # Path to curriculum file (adjust as needed)
    curriculum_path = Path("data/SWE-Bench-CL-Curriculum.json")

    # Initialize loader
    loader = SWEBenchCLLoader(curriculum_path)

    # Get all sequence names
    print("Available sequences:")
    sequence_names = loader.get_sequence_names()
    for name in sequence_names:
        print(f"  - {name}")

    # Load all sequences
    print("\nLoading all 8 sequences...")
    sequences = loader.load_all_sequences()
    print(f"Loaded {len(sequences)} sequences")

    # Display summary for each sequence
    print("\nSequence summaries:")
    for seq in sequences:
        print(f"\n{seq.sequence_name} ({seq.repo}):")
        print(f"  Tasks: {seq.task_count}")
        print(f"  First task: {seq.tasks[0].task_id}")
        print(f"  Last task: {seq.tasks[-1].task_id}")

    # Get a specific sequence
    print("\nLoading specific sequence 'django'...")
    django_seq = loader.get_sequence_by_name("django")
    if django_seq:
        print(f"Django sequence has {django_seq.task_count} tasks")
        print("\nFirst 3 tasks:")
        for task in django_seq.tasks[:3]:
            print(f"  {task.task_id} (index {task.sequence_index}, {task.difficulty_label})")
            print(f"    Issue: {task.issue_text[:80]}...")


if __name__ == "__main__":
    main()
