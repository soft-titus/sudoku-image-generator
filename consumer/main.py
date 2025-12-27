"""
Kafka consumer for Sudoku image generation messages.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
import math
from typing import Any, Dict, Optional

from confluent_kafka import Consumer, KafkaException, KafkaError, Producer
from pymongo import MongoClient
from pymongo.errors import PyMongoError

import config


def create_consumer() -> Consumer:
    """Create and return a configured Kafka consumer."""
    return Consumer(
        {
            "bootstrap.servers": config.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": config.KAFKA_CONSUMER_GROUP_NAME,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )


def extract_retry_count(msg) -> int:
    """Extract retry-count header from Kafka message."""
    if not msg.headers():
        return 0

    for key, value in msg.headers():
        if key == "retry-count":
            try:
                return int(value.decode("utf-8"))
            except (ValueError, AttributeError):
                return 0
    return 0


def is_heartbeat(payload: Dict[str, Any]) -> bool:
    """Return True if message is a heartbeat."""
    return payload.get("type") == "heartbeat"


def validate_puzzle_document(doc: dict) -> Optional[str]:
    """Validate puzzle document stored in MongoDB."""
    valid_sizes = {4, 9, 16}
    valid_levels = {"EASY", "MEDIUM", "HARD"}

    size = doc.get("puzzleSize")
    logging.debug("puzzleSize: %d", size)
    if size not in valid_sizes:
        return f"invalid puzzleSize: {size}"

    level = doc.get("level")
    logging.debug("level: %s", level)
    if level not in valid_levels:
        return f"invalid level: {doc.get('level')}"

    status = doc.get("status")
    logging.debug("status: %s", status)
    if status != "GENERATING_IMAGE":
        return f"invalid status: {doc.get('status')}"

    solution = doc.get("solution")
    logging.debug(
        "solution=%s",
        ";".join(",".join(map(str, row)) for row in solution),
    )
    if not isinstance(solution, list) or len(solution) != size:
        return "solution outer dimension mismatch"

    if any(not isinstance(row, list) or len(row) != size for row in solution):
        return "solution inner dimension mismatch"

    puzzle = doc.get("puzzle")
    logging.debug(
        "puzzle=%s",
        ";".join(",".join(map(str, row)) for row in puzzle),
    )
    if not isinstance(puzzle, list) or len(puzzle) != size:
        return "puzzle outer dimension mismatch"

    if any(not isinstance(row, list) or len(row) != size for row in puzzle):
        return "puzzle inner dimension mismatch"

    return None


def commit_message(consumer: Consumer, msg) -> None:
    """Commit Kafka message offset safely."""
    try:
        consumer.commit(msg)
    except KafkaException as exc:
        logging.warning("Commit failed: %s", exc)


def send_to_retriable(
    consumer: Consumer,
    producer: Producer,
    msg,
) -> None:
    """Send message to  be retry."""

    retry_count = extract_retry_count(msg)
    retry_count += 1

    backoff_seconds = min(
        (
            config.TASK_BASE_BACKOFF_SECONDS
            * math.pow(config.TASK_BASE_BACKOFF_MULTIPLIER, retry_count - 1)
        ),
        config.TASK_MAX_BACKOFF_SECONDS,
    )

    process_after = datetime.now(timezone.utc) + timedelta(seconds=int(backoff_seconds))

    headers = [
        ("retry-count", str(retry_count).encode("utf-8")),
        ("process-after", process_after.isoformat().encode("utf-8")),
        ("origin-topic", msg.topic().encode("utf-8")),
    ]

    producer.produce(
        topic=config.KAFKA_RETRIABLE_TOPIC,
        key=msg.key(),
        value=msg.value(),
        headers=headers,
    )

    producer.poll(0)
    commit_message(consumer, msg)
    logging.info(
        "Message sent to retriable topic retry-count=%d process-after=%s",
        retry_count,
        process_after.isoformat(),
    )


def send_to_dlq(consumer: Consumer, producer: Producer, msg, reason: str) -> None:
    """Send message to DLQ with failure reason."""
    try:
        payload = json.loads(msg.value().decode("utf-8")) if msg.value() else {}
    except (ValueError, AttributeError):
        payload = {"rawValue": str(msg.value())}

    payload.update(
        {
            "failedReason": reason,
            "failedAt": datetime.now(timezone.utc).isoformat(),
        }
    )

    producer.produce(
        topic=config.KAFKA_IMAGE_DLQ_TOPIC,
        key=msg.key(),
        value=json.dumps(payload).encode("utf-8"),
    )

    producer.poll(0)
    commit_message(consumer, msg)
    logging.info("Sent message to DLQ: %s", reason)


def process_message(payload: Dict[str, Any], _mongo_doc: dict) -> None:
    """Process a valid puzzle image generation request."""
    logging.info("Processing puzzleId=%s", payload.get("puzzleId"))


def handle_message(
    consumer: Consumer,
    producer: Producer,
    mongo_collection,
    msg,
) -> None:
    """Handle a single Kafka message."""
    try:
        payload = json.loads(msg.value().decode("utf-8")) if msg.value() else {}
    except (ValueError, AttributeError):
        send_to_dlq(consumer, producer, msg, "invalid JSON payload")
        return
    logging.debug("payload: %s", payload)

    if is_heartbeat(payload):
        logging.debug("Heartbeat received, skipping")
        commit_message(consumer, msg)
        return

    retry_count = extract_retry_count(msg)
    if retry_count >= config.TASK_MAX_RETRIES:
        send_to_dlq(
            consumer,
            producer,
            msg,
            f"retry-count exceeded: {retry_count}",
        )
        return

    puzzle_id = payload.get("puzzleId")
    if not puzzle_id:
        send_to_dlq(consumer, producer, msg, "missing puzzleId")
        return

    try:
        mongo_doc = mongo_collection.find_one({"puzzleId": puzzle_id})
    except PyMongoError:
        logging.exception("MongoDB error")
        send_to_retriable(consumer, producer, msg)
        return

    if not mongo_doc:
        send_to_dlq(
            consumer,
            producer,
            msg,
            f"puzzleId not found: {puzzle_id}",
        )
        return

    reason = validate_puzzle_document(mongo_doc)
    if reason:
        send_to_dlq(consumer, producer, msg, reason)
        return

    process_message(payload, mongo_doc)
    commit_message(consumer, msg)


def main() -> None:
    """Kafka consumer entry point."""
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logging.getLogger("pymongo").setLevel(logging.WARNING)

    consumer = create_consumer()
    consumer.subscribe([config.KAFKA_IMAGE_TOPIC])

    producer = Producer({"bootstrap.servers": config.KAFKA_BOOTSTRAP_SERVERS})

    mongo_client = MongoClient(
        config.MONGO_URI,
        serverSelectionTimeoutMS=10_000,
    )
    mongo_collection = mongo_client[config.MONGO_DB][config.MONGO_COLLECTION_NAME]

    logging.info("Kafka consumer started")

    try:
        while True:
            logging.debug("Polling for %ds", config.KAFKA_POOLING_INTERVAL_SECONDS)
            msg = consumer.poll(config.KAFKA_POOLING_INTERVAL_SECONDS)
            if msg is None:
                continue

            if msg.error():
                if (
                    msg.error().code()
                    == KafkaError._PARTITION_EOF  # pylint: disable=protected-access
                ):
                    continue
                raise KafkaException(msg.error())

            handle_message(consumer, producer, mongo_collection, msg)

    except KeyboardInterrupt:
        logging.info("Shutdown requested")

    finally:
        consumer.close()
        producer.flush()
        mongo_client.close()
        logging.info("Consumer shut down cleanly")


if __name__ == "__main__":
    main()
