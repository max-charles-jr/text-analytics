"""
Management command: process_novels

Runs the same conversion + analysis pipeline as the dashboard view, but
from the command line. Useful for (a) pre-warming the cache/audio files
before a demo, and (b) proving the conversion is done "programmatically"
via Python rather than by hand, independent of the web UI.

Usage:
    python manage.py process_novels
    python manage.py process_novels --skip-existing-audio
"""
import logging

from django.core.management.base import BaseCommand

from novels.services import s3_client, text_analysis, tts

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Convert every novel in /raw to MP3 in /audio and print token/entity counts."

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-existing-audio',
            action='store_true',
            help="Don't re-convert a novel if its MP3 already exists in /audio.",
        )

    def handle(self, *args, **options):
        text_analysis.ensure_nltk_resources()
        raw_keys = s3_client.list_raw_novels()
        if not raw_keys:
            self.stdout.write(self.style.WARNING('No .txt files found under /raw.'))
            return

        for raw_key in raw_keys:
            title = raw_key.rsplit('/', 1)[-1]
            self.stdout.write(f"\n=== {title} ===")
            text = s3_client.read_novel_text(raw_key)
            audio_key = s3_client.audio_key_for(raw_key)

            if options['skip_existing_audio'] and s3_client.audio_exists(audio_key):
                self.stdout.write(self.style.WARNING(f"  audio exists, skipping conversion: {audio_key}"))
            else:
                mp3_bytes = tts.synthesize_novel_to_mp3(text)
                s3_client.upload_audio(audio_key, mp3_bytes)
                self.stdout.write(self.style.SUCCESS(f"  converted -> s3://.../{audio_key} ({len(mp3_bytes)} bytes)"))

            tokens = text_analysis.tokenize_with_counts(text)
            entities = text_analysis.named_entities_with_counts(text)
            self.stdout.write(f"  tokens: {sum(tokens.values())} total, {len(tokens)} unique")
            self.stdout.write(f"  top 10 tokens: {tokens.most_common(10)}")
            self.stdout.write(f"  entities: {sum(entities.values())} total, {len(entities)} unique")
            self.stdout.write(f"  top 10 entities: {entities.most_common(10)}")
