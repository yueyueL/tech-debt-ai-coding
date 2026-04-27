"""
I/O utilities for saving and loading data.
"""
import json
import csv
from pathlib import Path
from typing import Dict, List, Any


def save_json(data: Any, filepath: str) -> None:
    """Save data to JSON file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)


def load_json(filepath: str) -> Any:
    """Load data from JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_csv(data: List[Dict], filepath: str, fieldnames: List[str] = None) -> None:
    """Save list of dicts to CSV file."""
    if not data:
        return
        
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if fieldnames is None:
        fieldnames = list(data[0].keys())
    
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
