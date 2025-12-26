"""
Kafka producer for Sudoku image generation tasks using confluent-kafka.

This script sends a single Kafka message containing a puzzle ID.
It is intended for testing and local development purposes.
"""

import argparse
import json
import logging
import random
import string
from typing import Optional

from confluent_kafka import Producer

import config


def generate_random_id(length: int = 5) -> str:
    """
    Generate a random alphanumeric string.

    Args:
        length: Length of the generated ID

    Returns:
        Random string
    """
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Sudoku Kafka producer")
    parser.add_argument(
        "--puzzle-id",
        dest="puzzle_id",
        required=False,
        help="Puzzle ID to send (random if not provided)",
    )
    parser.add_argument(
        "--retry-count",
        dest="retry_count",
        type=int,
        required=False,
        help="Retry count header value (random if not provided)",
    )
    return parser.parse_args()


def resolve_retry_count(retry_count: Optional[int]) -> int:
    """
    Resolve retry count value.

    If not provided, generate a random retry count less than TASK_MAX_RETRIES.

    Args:
        retry_count: Retry count from CLI

    Returns:
        Resolved retry count
    """
    if retry_count is not None:
        return retry_count

    return random.randint(0, config.TASK_MAX_RETRIES - 1)


def create_producer() -> Producer:
    """
    Create and return a Confluent Kafka producer instance.

    Returns:
        Kafka Producer
    """
    conf = {
        "bootstrap.servers": config.KAFKA_BOOTSTRAP_SERVERS,
    }
    return Producer(**conf)


def delivery_report(err, msg) -> None:
    """
    Callback called once a message has been delivered or failed.

    Args:
        err: Error info (None if successful)
        msg: The original message
    """
    if err is not None:
        logging.error("Message delivery failed: %s", err)
    else:
        logging.info("Message delivered to %s [%d]", msg.topic(), msg.partition())


def main() -> None:
    """
    Main entry point for the Kafka producer.
    """
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    args = parse_args()

    puzzle_id = args.puzzle_id or generate_random_id()
    retry_count = resolve_retry_count(args.retry_count)

    producer = create_producer()

    message_value = {"puzzleId": puzzle_id}
    message_headers = [("retry-count", str(retry_count).encode("utf-8"))]

    logging.info(
        "Sending message puzzleId=%s retryCount=%d",
        puzzle_id,
        retry_count,
    )

    producer.produce(
        topic=config.KAFKA_IMAGE_TOPIC,
        key=puzzle_id.encode("utf-8"),
        value=json.dumps(message_value).encode("utf-8"),
        headers=message_headers,
        callback=delivery_report,
    )

    producer.flush()
    logging.info("Message sent successfully")


if __name__ == "__main__":
    main()
