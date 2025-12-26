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
import random
import sys
from datetime import datetime, timezone
from typing import List

from pymongo import MongoClient
from pymongo.errors import PyMongoError

import config


def parse_csv_numbers(value: str) -> List[int]:
    """
    Parse a comma-separated string into a list of integers.

    This function is intentionally permissive. Any parsing error
    results in a best-effort output or an empty list.

    Args:
        value: Comma-separated string of numbers.

    Returns:
        List of integers.
    """
    try:
        return [int(item.strip()) for item in value.split(",")]
    except Exception:  # pylint: disable=broad-except
        return []


def generate_random_solution(puzzle_size: int) -> List[int]:
    """
    Generate a random solution matrix.

    The generated data is NOT guaranteed to be a valid Sudoku solution.
    It is intended purely for testing downstream consumers.

    Args:
        puzzle_size: Size of the puzzle (e.g., 4, 9, 16).

    Returns:
        A flat list of random integers.
    """
    total = puzzle_size * puzzle_size
    return [random.randint(1, puzzle_size) for _ in range(total)]


def generate_random_puzzle(solution: List[int]) -> List[int]:
    """
    Generate a puzzle by removing approximately 50% of the solution values.

    Removed values are replaced with zeroes.

    Args:
        solution: Flat list representing the solution.

    Returns:
        A modified puzzle list.
    """
    puzzle = solution.copy()
    total = len(puzzle)
    remove_count = total // 2

    for index in random.sample(range(total), remove_count):
        puzzle[index] = 0

    return puzzle


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Sudoku test data ingester")

    parser.add_argument(
        "--puzzle-id",
        required=True,
        help="Puzzle ID (required)",
    )
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
    parser.add_argument(
        "--solution",
        help="Comma-separated sudoku solution",
    )
    parser.add_argument(
        "--puzzle",
        help="Comma-separated sudoku puzzle",
    )

    return parser.parse_args()


def main() -> None:
    """
    Entry point for the ingester.

    Inserts or updates a Sudoku puzzle document in MongoDB using upsert.
    """
    args = parse_arguments()

    # Solution handling
    solution = (
        parse_csv_numbers(args.solution)
        if args.solution
        else generate_random_solution(args.puzzle_size)
    )

    # Puzzle handling
    puzzle = (
        parse_csv_numbers(args.puzzle)
        if args.puzzle
        else generate_random_puzzle(solution)
    )

    try:
        client = MongoClient(
            config.MONGO_URI,
            serverSelectionTimeoutMS=10_000,
        )
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

        result = collection.update_one(
            filter_doc,
            update_doc,
            upsert=True,
        )

        if result.matched_count > 0:
            print(f"Updated puzzle with ID {args.puzzle_id}")
        elif result.upserted_id is not None:
            print(f"Inserted puzzle with ID {args.puzzle_id}")
        else:
            print(f"No changes made to puzzle with ID {args.puzzle_id}")

    except PyMongoError as exc:
        print(f"MongoDB error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            client.close()
        except Exception:  # pylint: disable=broad-except
            pass


if __name__ == "__main__":
    main()
