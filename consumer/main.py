"""Kafka consumer for Sudoku image generation messages."""

import json
import logging
from typing import Any, Dict, Optional

from confluent_kafka import Consumer, KafkaException, KafkaError

import config


def create_consumer() -> Consumer:
    """Create and return a configured Kafka consumer."""
    consumer_config: Dict[str, Any] = {
        "bootstrap.servers": config.KAFKA_BOOTSTRAP_SERVERS,
        "group.id": config.KAFKA_CONSUMER_GROUP_NAME,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,  # Manual commit
    }
    return Consumer(consumer_config)


def process_message(payload: Dict[str, Any], key: Optional[str]) -> None:
    """Placeholder for processing the Kafka message."""
    logging.debug("Processing payload with key=%s: %s", key, payload)


def main() -> None:
    """Main entry point for the Kafka consumer."""
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    consumer = create_consumer()
    consumer.subscribe([config.KAFKA_IMAGE_TOPIC])

    logging.info("Kafka consumer started")
    logging.info("Subscribed to topic=%s", config.KAFKA_IMAGE_TOPIC)

    try:
        while True:
            logging.debug("Pooling for %ds", config.KAFKA_POOLING_INTERVAL_SECONDS)
            msg = consumer.poll(timeout=config.KAFKA_POOLING_INTERVAL_SECONDS)
            if msg is None:
                continue

            if msg.error():
                if (
                    msg.error().code()
                    == KafkaError._PARTITION_EOF  # pylint: disable=protected-access
                ):
                    continue
                raise KafkaException(msg.error())

            try:
                value_bytes = msg.value()
                value_str = value_bytes.decode("utf-8") if value_bytes else "{}"
                payload: Dict[str, Any] = json.loads(value_str)
                key_str: Optional[str] = (
                    msg.key().decode("utf-8") if msg.key() else None
                )
            except Exception:  # pylint: disable=broad-except
                logging.exception("Failed to decode Kafka message")
                consumer.commit(msg)
                continue

            logging.info(
                "Received message topic=%s partition=%s offset=%s key=%s",
                msg.topic(),
                msg.partition(),
                msg.offset(),
                key_str,
            )

            logging.debug("Payload: %s", payload)

            process_message(payload, key_str)
            consumer.commit(msg)

    except KeyboardInterrupt:
        logging.info("Shutdown requested by user")

    finally:
        consumer.close()
        logging.info("Kafka consumer closed")


if __name__ == "__main__":
    main()
