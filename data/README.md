# Data Directory

This directory contains the SWE-Bench-CL curriculum data file.

## Required File

Place the official `SWE-Bench-CL-Curriculum.json` file in this directory.

The curriculum file should contain:
- Exactly 8 sequences
- Each sequence with at least 15 tasks
- All required task fields (task_id, repo, base_commit, issue_text, test_patch, gold_patch, created_at, sequence_index, difficulty_label)

## File Structure

```
data/
├── README.md                          # This file
└── SWE-Bench-CL-Curriculum.json      # Official curriculum (not in git)
```

## Source

The official SWE-Bench-CL curriculum can be obtained from:
https://github.com/thomasjoshi/agents-never-forget

## Usage

```python
from pathlib import Path
from src.benchmark import SWEBenchCLLoader

# Load curriculum
loader = SWEBenchCLLoader("data/SWE-Bench-CL-Curriculum.json")
sequences = loader.load_all_sequences()

# Access sequences
for seq in sequences:
    print(f"{seq.sequence_name}: {seq.task_count} tasks")
```

See `examples/loader_usage.py` for a complete example.
