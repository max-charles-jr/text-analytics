"""
Text-to-speech conversion using AWS Polly.

Design note (see SWDD Section 3.3, Design Rationale):
Polly's synchronous SynthesizeSpeech API caps input at 3,000 billed
characters for a neural voice. Full novels are far larger than that (Moby
Dick is roughly 1.2 million characters), so a novel cannot be sent to Polly
in a single call. Rather than use the asynchronous StartSpeechSynthesisTask
API (still capped at 100,000 characters per task, which still requires
chunking for the longest novels, plus S3-task polling overhead), this
module chunks the novel into speech-safe segments, calls the synchronous
API once per chunk, and concatenates the returned MP3 audio streams into a
single MP3 file. MP3 supports this kind of frame-level concatenation
because each frame carries its own header, so the concatenated file plays
back as one continuous track in every player/browser we tested it in.
"""
import logging
import re

import boto3
from django.conf import settings

logger = logging.getLogger(__name__)

_polly = boto3.client('polly', region_name=settings.AWS_REGION)

# Stay safely under Polly's 3,000-billed-character ceiling for neural
# voices; this leaves headroom for multi-byte characters, which Polly
# bills by UTF-8 byte, not by Python string length.
MAX_CHUNK_CHARS = 2800

_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+')


def _chunk_text(text, max_chars=MAX_CHUNK_CHARS):
    """Split text into <= max_chars chunks, breaking on sentence boundaries
    where possible so Polly doesn't cut off mid-sentence."""
    sentences = _SENTENCE_BOUNDARY.split(text)
    chunks = []
    current = []
    current_len = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        # A single sentence longer than the limit (rare, but Gutenberg
        # front-matter sometimes has run-on legal text) is hard-split.
        while len(sentence) > max_chars:
            chunks.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if current_len + len(sentence) + 1 > max_chars:
            chunks.append(' '.join(current))
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len += len(sentence) + 1

    if current:
        chunks.append(' '.join(current))
    return chunks


def synthesize_novel_to_mp3(novel_text):
    """Convert a full novel's text into a single concatenated MP3 byte string."""
    chunks = _chunk_text(novel_text)
    logger.info("Synthesizing %d characters across %d Polly chunks", len(novel_text), len(chunks))

    audio_parts = []
    for i, chunk in enumerate(chunks):
        try:
            response = _polly.synthesize_speech(
                Text=chunk,
                OutputFormat='mp3',
                VoiceId=settings.POLLY_VOICE_ID,
                Engine=settings.POLLY_ENGINE,
            )
        except _polly.exceptions.TextLengthExceededException:
            logger.exception("Polly rejected chunk %d/%d as too long (%d chars)", i + 1, len(chunks), len(chunk))
            raise
        except Exception:
            logger.exception("Polly synthesis failed on chunk %d/%d", i + 1, len(chunks))
            raise
        audio_parts.append(response['AudioStream'].read())

    return b''.join(audio_parts)
