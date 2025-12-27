"""
Configuration, read from environment variables
"""

import os


def parse_rgb(value: str) -> tuple[int, int, int]:
    """Parse RGB string to tuple."""
    value = value.strip().strip("()")
    r, g, b = map(int, value.split(","))
    return (r, g, b)


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

KAFKA_CONSUMER_GROUP_NAME = os.getenv(
    "KAFKA_CONSUMER_GROUP_NAME",
    "sudoku.image.generate.group",
)

KAFKA_POOLING_INTERVAL_SECONDS = int(os.getenv("KAFKA_POOLING_INTERVAL_SECONDS", "15"))

KAFKA_BROKER_HOST = os.getenv("KAFKA_BROKER_HOST", "kafka")
KAFKA_BROKER_PORT = os.getenv("KAFKA_BROKER_PORT", "9092")

KAFKA_BOOTSTRAP_SERVERS = f"{KAFKA_BROKER_HOST}:{KAFKA_BROKER_PORT}"

KAFKA_RETRIABLE_TOPIC = os.getenv("KAFKA_RETRIABLE_TOPIC", "retriable")
KAFKA_IMAGE_TOPIC = os.getenv("KAFKA_IMAGE_TOPIC", "sudoku.image.generate")
KAFKA_IMAGE_DLQ_TOPIC = os.getenv(
    "KAFKA_IMAGE_DLQ_TOPIC",
    "sudoku.image.generate.dlq",
)

TASK_MAX_RETRIES = int(os.getenv("TASK_MAX_RETRIES", "3"))
TASK_BASE_BACKOFF_SECONDS = int(os.getenv("TASK_BASE_BACKOFF_SECONDS", "15"))
TASK_BASE_BACKOFF_MULTIPLIER = int(os.getenv("TASK_BASE_BACKOFF_MULTIPLIER", "2"))
TASK_MAX_BACKOFF_SECONDS = int(os.getenv("TASK_MAX_BACKOFF_SECONDS", "300"))

MONGO_HOST = os.getenv("MONGO_HOST", "mongodb")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_USER = os.getenv("MONGO_USER", "sudoku")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "Sudoku123")
MONGO_DB = os.getenv("MONGO_DB", "sudoku")
MONGO_OPTIONS = os.getenv("MONGO_OPTIONS")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "puzzle")

MONGO_URI = (
    f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}" f"@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"
)
if MONGO_OPTIONS:
    MONGO_URI = f"{MONGO_URI}?{MONGO_OPTIONS.lstrip('?')}"

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "sudoku")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "verySECRET123")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")

S3_PROTOCOL = os.getenv("S3_PROTOCOL", "https")
S3_HOST = os.getenv("S3_HOST")
S3_PORT = os.getenv("S3_PORT")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "sudoku")


S3_ENDPOINT_URL = ""
if S3_HOST:
    S3_ENDPOINT_URL = f"{S3_PROTOCOL}://{S3_HOST}"
    if S3_PORT:
        S3_ENDPOINT_URL = f"{S3_ENDPOINT_URL}:{S3_PORT}"

SUDOKU_CELL_SIZE_PX = int(os.getenv("SUDOKU_CELL_SIZE_PX", "133"))
SUDOKU_THICK_LINE_PX = int(os.getenv("SUDOKU_THICK_LINE_PX", "5"))
SUDOKU_THIN_LINE_PX = int(os.getenv("SUDOKU_THIN_LINE_PX", "2"))
SUDOKU_FONT_SIZE_PX = int(os.getenv("SUDOKU_FONT_SIZE_PX", "86"))
SUDOKU_CELL_FIRST_COLOR_RGB = parse_rgb(
    os.getenv("SUDOKU_CELL_FIRST_COLOR_RGB", "255,255,255")
)
SUDOKU_CELL_SECOND_COLOR_RGB = parse_rgb(
    os.getenv("SUDOKU_CELL_SECOND_COLOR_RGB", "235,235,235")
)
SUDOKU_LINE_COLOR_RGB = parse_rgb(os.getenv("SUDOKU_LINE_COLOR_RGB", "0,0,0"))
SUDOKU_TEXT_COLOR_RGB = parse_rgb(os.getenv("SUDOKU_TEXT_COLOR_RGB", "0,0,0"))
SUDOKU_IMAGE_DPI = int(os.getenv("SUDOKU_IMAGE_DPI", "300"))
SUDOKU_TEXT_FONT_PATH = "fonts/DejaVuSans-Bold.ttf"
