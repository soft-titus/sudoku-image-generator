"""
Helper functions to upload images to S3 or MinIO using botocore.
"""

import io
import logging

import botocore.session
from botocore.client import BaseClient

import config


def get_s3_client() -> BaseClient:
    """Return a boto3/botocore S3 client, using custom endpoint if provided."""
    session = botocore.session.get_session()
    s3_config = {
        "aws_access_key_id": config.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": config.AWS_SECRET_ACCESS_KEY,
        "region_name": config.AWS_REGION,
    }
    if config.S3_ENDPOINT_URL:
        s3_config["endpoint_url"] = config.S3_ENDPOINT_URL
    return session.create_client("s3", **s3_config)


def upload_image(
    image: "PIL.Image.Image",
    object_name: str,
    bucket: str,
) -> None:
    """
    Upload a PIL image to S3 / MinIO as PNG.

    Args:
        image: PIL.Image object
        object_name: S3 object key (filename in bucket)
        bucket: S3 bucket name
    """
    client = get_s3_client()
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    try:
        client.put_object(
            Bucket=bucket, Key=object_name, Body=buffer, ContentType="image/png"
        )
        logging.info("Uploaded image to s3://%s/%s", bucket, object_name)
    except Exception as e:
        logging.exception("Failed to upload image %s to bucket %s", object_name, bucket)
        raise e
