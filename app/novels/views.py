import logging
import time

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render

from .services import s3_client, text_analysis, tts

logger = logging.getLogger(__name__)


def healthz(request):
    """Lightweight liveness/readiness endpoint for the ECS/ALB health check."""
    return JsonResponse({"status": "ok"})


def _process_novel(raw_key):
    """Run TTS conversion (if needed) and text analysis for one novel.
    Returns a dict consumed by the dashboard template."""
    cache_key = f"novel-result::{raw_key}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    title = raw_key.rsplit('/', 1)[-1].rsplit('.', 1)[0].replace('_', ' ')
    logger.info("Processing novel: %s", title)
    started = time.monotonic()

    text = s3_client.read_novel_text(raw_key)

    # --- Step 1: TTS conversion, writing MP3s into /audio -----------------
    audio_key = s3_client.audio_key_for(raw_key)
    already_converted = s3_client.audio_exists(audio_key)
    if not already_converted:
        mp3_bytes = tts.synthesize_novel_to_mp3(text)
        s3_client.upload_audio(audio_key, mp3_bytes)
        conversion_note = f"Converted just now and uploaded to s3://.../{audio_key}"
    else:
        conversion_note = f"Already present at s3://.../{audio_key} (skipped re-conversion)"

    # --- Step 2: tokenization + named-entity extraction --------------------
    text_analysis.ensure_nltk_resources()
    token_counts = text_analysis.tokenize_with_counts(text)
    entity_counts = text_analysis.named_entities_with_counts(text)

    result = {
        'title': title,
        'raw_key': raw_key,
        'audio_key': audio_key,
        'converted': True,
        'already_converted': already_converted,
        'conversion_note': conversion_note,
        'char_count': len(text),
        'token_total': sum(token_counts.values()),
        'unique_token_count': len(token_counts),
        'top_tokens': token_counts.most_common(),
        'entity_total': sum(entity_counts.values()),
        'unique_entity_count': len(entity_counts),
        'top_entities': entity_counts.most_common(),
        'seconds': round(time.monotonic() - started, 1),
    }
    # Cache for an hour; long enough to avoid re-processing on every
    # dashboard refresh, short enough that a redeploy/restart picks up any
    # new novels added to /raw without needing a manual cache-bust.
    cache.set(cache_key, result, timeout=3600)
    return result


def dashboard(request):
    from django.conf import settings

    errors = []
    results = []
    try:
        raw_keys = s3_client.list_raw_novels()
    except Exception as exc:  # noqa: BLE001 - surfaced to the page, not swallowed
        logger.exception("Could not list novels in bucket")
        return render(request, 'novels/dashboard.html', {
            'errors': [f"Could not reach S3 bucket '{settings.NOVELS_BUCKET}': {exc}"],
            'results': [],
            'bucket': settings.NOVELS_BUCKET,
        })

    if not raw_keys:
        errors.append(
            f"No .txt files found under s3://{settings.NOVELS_BUCKET}/{settings.RAW_PREFIX} yet."
        )

    for raw_key in raw_keys:
        try:
            results.append(_process_novel(raw_key))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to process %s", raw_key)
            errors.append(f"{raw_key}: {exc}")

    context = {
        'bucket': settings.NOVELS_BUCKET,
        'results': results,
        'errors': errors,
        'max_table_rows': settings.MAX_TABLE_ROWS,
        'novel_count': len(results),
    }
    return render(request, 'novels/dashboard.html', context)
