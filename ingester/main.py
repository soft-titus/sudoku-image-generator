"""
Sudoku test data ingester.

This module inserts or updates Sudoku puzzle data in MongoDB.
It is intentionally permissive and designed for testing purposes only.

Behavior:
- `puzzle-id` is required
- All other fields are optional and loosely validated
- If solution is not provided, random numbers are generated
- If puzzle is not provided, ~50% of solution values are removed
- Invalid or malformed data is allowed to test consumer robustness
"""

import argparse
import logging
import random
import sys
from datetime import datetime, timezone
from typing import List

from pymongo import MongoClient
from pymongo.errors import PyMongoError

import config


def parse_csv_numbers(value: str) -> List[int]:
    """Parse a comma-separated string into a flat list of integers."""
    try:
        return [int(item.strip()) for item in value.split(",")]
    except Exception:  # pylint: disable=broad-except
        logging.warning("Failed to parse CSV numbers: %s", value)
        return []


def to_matrix(flat: List[int], puzzle_size: int) -> List[List[int]]:
    """
    Convert a flat list into a 2D matrix.

    If the flat list length is invalid, return an empty matrix.
    """
    expected = puzzle_size * puzzle_size
    if len(flat) != expected:
        logging.warning(
            "Invalid flat list length=%d expected=%d",
            len(flat),
            expected,
        )
        return []

    return [
        flat[row * puzzle_size : (row + 1) * puzzle_size] for row in range(puzzle_size)
    ]


def generate_random_solution(puzzle_size: int) -> List[List[int]]:
    """Generate a random 2D solution matrix (not guaranteed valid Sudoku)."""
    return [
        [random.randint(1, puzzle_size) for _ in range(puzzle_size)]
        for _ in range(puzzle_size)
    ]


def generate_random_puzzle(solution: List[List[int]]) -> List[List[int]]:
    """
    Generate a puzzle by removing ~50% of values from the solution.
    Removed values are replaced with zeroes.
    """
    puzzle = [row.copy() for row in solution]
    puzzle_size = len(puzzle)
    total_cells = puzzle_size * puzzle_size
    remove_count = total_cells // 2

    indices = random.sample(range(total_cells), remove_count)
    for idx in indices:
        row = idx // puzzle_size
        col = idx % puzzle_size
        puzzle[row][col] = 0

    return puzzle


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Sudoku test data ingester")
    parser.add_argument("--puzzle-id", required=True, help="Puzzle ID (required)")
    parser.add_argument(
        "--puzzle-size",
        type=int,
        default=9,
        help="Puzzle size (default: 9)",
    )
    parser.add_argument(
        "--level",
        default="EASY",
        help="Puzzle difficulty level (default: EASY)",
    )
    parser.add_argument(
        "--status",
        default="GENERATING_IMAGE",
        help="Puzzle status (default: GENERATING_IMAGE)",
    )
    parser.add_argument("--solution", help="Comma-separated sudoku solution")
    parser.add_argument("--puzzle", help="Comma-separated sudoku puzzle")
    return parser.parse_args()


def main() -> None:
    """Entry point for the ingester."""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.getLogger("pymongo").setLevel(logging.WARNING)

    args = parse_arguments()

    # Solution handling
    if args.solution:
        flat_solution = parse_csv_numbers(args.solution)
        solution = to_matrix(flat_solution, args.puzzle_size)
    else:
        solution = generate_random_solution(args.puzzle_size)

    # Puzzle handling
    if args.puzzle:
        flat_puzzle = parse_csv_numbers(args.puzzle)
        puzzle = to_matrix(flat_puzzle, args.puzzle_size)
    else:
        puzzle = generate_random_puzzle(solution)

    try:
        client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=10_000)
        collection = client[config.MONGO_DB][config.MONGO_COLLECTION_NAME]

        now = datetime.now(timezone.utc)

        filter_doc = {"puzzleId": args.puzzle_id}
        update_doc = {
            "$set": {
                "puzzleSize": args.puzzle_size,
                "level": args.level,
                "status": args.status,
                "solution": solution,
                "puzzle": puzzle,
                "updatedAt": now,
            },
            "$setOnInsert": {
                "createdAt": now,
            },
        }

        result = collection.update_one(filter_doc, update_doc, upsert=True)

        if result.matched_count > 0:
            logging.info("Updated puzzle with ID %s", args.puzzle_id)
        elif result.upserted_id is not None:
            logging.info("Inserted puzzle with ID %s", args.puzzle_id)
        else:
            logging.info("No changes made to puzzle with ID %s", args.puzzle_id)

    except PyMongoError as exc:
        logging.error("MongoDB error: %s", exc, exc_info=True)
        sys.exit(1)
    finally:
        try:
            client.close()
        except Exception:  # pylint: disable=broad-except
            pass


if __name__ == "__main__":
    main()
