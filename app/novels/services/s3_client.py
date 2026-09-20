"""
Thin wrapper around boto3's S3 client for the novels bucket.

Kept separate from views/business logic so the rest of the app never talks
to boto3 directly -- this is the single place that knows about bucket
names, prefixes, and S3 error handling.
"""
import logging

import boto3
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)

_s3 = boto3.client('s3', region_name=settings.AWS_REGION)


def list_raw_novels():
    """Return the list of .txt object keys under the raw/ prefix."""
    keys = []
    paginator = _s3.get_paginator('list_objects_v2')
    try:
        for page in paginator.paginate(Bucket=settings.NOVELS_BUCKET, Prefix=settings.RAW_PREFIX):
            for obj in page.get('Contents', []):
                if obj['Key'].lower().endswith('.txt'):
                    keys.append(obj['Key'])
    except ClientError:
        logger.exception("Failed to list raw novels in bucket %s", settings.NOVELS_BUCKET)
        raise
    return sorted(keys)


def read_novel_text(key):
    """Download a novel text file from S3 and decode it as UTF-8."""
    try:
        obj = _s3.get_object(Bucket=settings.NOVELS_BUCKET, Key=key)
        raw = obj['Body'].read()
    except ClientError:
        logger.exception("Failed to read %s from bucket %s", key, settings.NOVELS_BUCKET)
        raise
    # Project Gutenberg texts are UTF-8; fall back to latin-1 defensively
    # for any older/legacy encodings so a single bad file can't 500 the page.
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        logger.warning("UTF-8 decode failed for %s, falling back to latin-1", key)
        return raw.decode('latin-1')


def audio_key_for(raw_key):
    """Map a raw/<title>.txt key to its audio/<title>.mp3 destination key."""
    filename = raw_key.rsplit('/', 1)[-1]
    stem = filename.rsplit('.', 1)[0]
    return f"{settings.AUDIO_PREFIX}{stem}.mp3"


def audio_exists(audio_key):
    try:
        _s3.head_object(Bucket=settings.NOVELS_BUCKET, Key=audio_key)
        return True
    except ClientError as exc:
        if exc.response['Error']['Code'] in ('404', 'NoSuchKey'):
            return False
        logger.exception("Unexpected error checking for %s", audio_key)
        raise


def upload_audio(audio_key, mp3_bytes):
    try:
        _s3.put_object(
            Bucket=settings.NOVELS_BUCKET,
            Key=audio_key,
            Body=mp3_bytes,
            ContentType='audio/mpeg',
        )
        logger.info("Uploaded %s (%d bytes) to s3://%s", audio_key, len(mp3_bytes), settings.NOVELS_BUCKET)
    except ClientError:
        logger.exception("Failed to upload %s to bucket %s", audio_key, settings.NOVELS_BUCKET)
        raise
