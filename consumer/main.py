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
from PIL import Image, ImageDraw, ImageFont

import config
from consumer import s3


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
    try:
        logging.debug(
            "solution=%s",
            ";".join(",".join(map(str, row)) for row in solution),
        )
    except TypeError:
        logging.debug("solution not an 2D Array")
    if not isinstance(solution, list) or len(solution) != size:
        return "solution outer dimension mismatch"

    if any(not isinstance(row, list) or len(row) != size for row in solution):
        return "solution inner dimension mismatch"

    if any(
        not isinstance(cell, int) or cell < 1 or cell > size
        for row in solution
        for cell in row
    ):
        return "invalid solution cell value"

    puzzle = doc.get("puzzle")
    try:
        logging.debug(
            "puzzle=%s",
            ";".join(",".join(map(str, row)) for row in puzzle),
        )
    except TypeError:
        logging.debug("puzzle not an 2D Array")
    if not isinstance(puzzle, list) or len(puzzle) != size:
        return "puzzle outer dimension mismatch"

    if any(not isinstance(row, list) or len(row) != size for row in puzzle):
        return "puzzle inner dimension mismatch"

    if any(
        not isinstance(cell, int) or cell < 0 or cell > size
        for row in puzzle
        for cell in row
    ):
        return "invalid puzzle cell value"

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
    """Send message to be retried"""

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

    headers = list(msg.headers() or [])
    headers = [(k, v) for k, v in headers if k not in {"retry-count", "process-after"}]
    headers.extend(
        [
            ("retry-count", str(retry_count).encode()),
            ("process-after", process_after.isoformat().encode()),
            ("origin-topic", msg.topic().encode()),
        ]
    )

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


def process_message(payload: dict, mongo_doc: dict, mongo_collection) -> None:
    """
    Process a valid puzzle image generation request.

    Args:
        payload (dict): Kafka message payload, must contain "puzzleId".
        mongo_doc (dict): MongoDB document for the puzzle.
        mongo_collection: PyMongo collection object to update the document.

    Raises:
        Exception: If image generation, upload, or Mongo update fails.
    """
    puzzle_id = payload.get("puzzleId")

    board_size = mongo_doc.get("puzzleSize")
    solution = mongo_doc.get("solution")
    puzzle = mongo_doc.get("puzzle")

    try:
        solution_image = draw_sudoku_board(board_size, solution)
        puzzle_image = draw_sudoku_board(board_size, puzzle)
        logging.info("Generated puzzle and solution images for puzzleId=%s", puzzle_id)
    except Exception as e:
        logging.exception("Failed to generate Sudoku images for puzzleId=%s", puzzle_id)
        raise e

    solution_key = f"{puzzle_id}/solution.png"
    puzzle_key = f"{puzzle_id}/puzzle.png"
    bucket_name = config.S3_BUCKET_NAME

    try:
        s3.upload_image(solution_image, solution_key, bucket_name)
        s3.upload_image(puzzle_image, puzzle_key, bucket_name)
    except Exception as e:
        logging.exception("Failed to upload images for puzzleId=%s", puzzle_id)
        raise e

    try:
        mongo_collection.update_one(
            {"puzzleId": puzzle_id},
            {
                "$set": {
                    "solutionImagePath": solution_key,
                    "puzzleImagePath": puzzle_key,
                    "status": "SUCCESS",
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
        )
        logging.info(
            "Updated Mongo document for puzzleId=%s with image paths and status SUCCESS",
            puzzle_id,
        )
    except PyMongoError as e:
        logging.exception(
            "Failed to update MongoDB document for puzzleId=%s", puzzle_id
        )
        raise e


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

    try:
        process_message(payload, mongo_doc, mongo_collection)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.exception("Processing failed: %s", e)
        send_to_retriable(consumer, producer, msg)
        return

    commit_message(consumer, msg)
    return


# pylint: disable=too-many-locals
def draw_sudoku_board(
    board_size: int,
    board_data: list[list[int]],
) -> Image.Image:
    """
    Draw a Sudoku board with numbers as a PIL Image.

    This function:
    - Draws box-based shading (alternating colors per subgrid/box)
    - Draws thick and thin grid lines
    - Draws numbers centered in each cell
    - Skips empty cells (0)

    Args:
        board_size: Number of cells per row/column (e.g., 4, 9, 16).
        board_data: 2D list of integers representing the Sudoku board.
            Empty cells must be 0. Must match board_size (board_size x board_size).

    Returns:
        A PIL.Image object of the Sudoku board with numbers drawn.
    """

    cell_size = config.SUDOKU_CELL_SIZE_PX
    thin_line = config.SUDOKU_THIN_LINE_PX
    thick_line = config.SUDOKU_THICK_LINE_PX

    box_size = int(board_size**0.5)

    line_widths = [
        thick_line if i % box_size == 0 else thin_line for i in range(board_size + 1)
    ]

    total_line_width = sum(line_widths)
    total_image_size = board_size * cell_size + total_line_width

    image = Image.new("RGB", (total_image_size, total_image_size))
    draw = ImageDraw.Draw(image)

    box_color_1 = config.SUDOKU_CELL_FIRST_COLOR_RGB
    box_color_2 = config.SUDOKU_CELL_SECOND_COLOR_RGB
    grid_line_color = config.SUDOKU_LINE_COLOR_RGB
    text_color = config.SUDOKU_TEXT_COLOR_RGB
    font = ImageFont.truetype(config.SUDOKU_TEXT_FONT_PATH, config.SUDOKU_FONT_SIZE_PX)

    y_offset = line_widths[0]
    for row in range(board_size):
        x_offset = line_widths[0]
        for col in range(board_size):
            x1 = x_offset + cell_size
            y1 = y_offset + cell_size

            box_row = row // box_size
            box_col = col // box_size

            fill_color = box_color_1 if (box_row + box_col) % 2 == 0 else box_color_2
            draw.rectangle([x_offset, y_offset, x1, y1], fill=fill_color)

            number = str(board_data[row][col])
            draw_sudoku_text(
                draw, x_offset, y_offset, cell_size, number, font, text_color
            )

            x_offset += cell_size + line_widths[col + 1]
        y_offset += cell_size + line_widths[row + 1]

    current_pos = 0
    for idx, width in enumerate(line_widths):
        draw.rectangle(
            [current_pos, 0, current_pos + width - 1, total_image_size - 1],
            fill=grid_line_color,
        )
        draw.rectangle(
            [0, current_pos, total_image_size - 1, current_pos + width - 1],
            fill=grid_line_color,
        )

        current_pos += width
        if idx < board_size:
            current_pos += cell_size

    return image


# pylint: disable=too-many-arguments,too-many-positional-arguments
def draw_sudoku_text(
    draw: ImageDraw.Draw,
    x: int,
    y: int,
    cell_size: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    text_color: tuple[int, int, int],
) -> None:
    """
    Draw a number centered inside a Sudoku cell.

    Empty cells (represented by "0" or blank strings) are skipped.

    Args:
        draw: PIL ImageDraw object used to draw on the image.
        x: Top-left x-coordinate of the cell (including line offset).
        y: Top-left y-coordinate of the cell (including line offset).
        cell_size: Size of the cell in pixels.
        text: The text/number to draw. "0" or empty strings are ignored.
        font: PIL ImageFont object to use for the text.
        text_color: RGB tuple specifying the text color.
    """

    if text == "0" or text.strip() == "":
        return

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    text_x = x + (cell_size - text_width) / 2
    text_y = y + (cell_size - text_height) / 2

    draw.text((text_x, text_y), text, font=font, fill=text_color)


def main() -> None:
    """Kafka consumer entry point."""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
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
