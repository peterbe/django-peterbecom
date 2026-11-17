import datetime
import re
import time

from django.conf import settings
from django.db.models import F
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import periodic_task, task

from peterbecom.chiveproxy.image_transcript import get_image_transcript
from peterbecom.chiveproxy.models import BannedUrlPattern, Card, Picture
from peterbecom.chiveproxy.preload_image_proxies import (
    load_all_image_proxies,
)


def _is_banned(
    banned_part: str | re.Pattern, needle: str, case_insensitive: bool = False
) -> bool:
    if isinstance(banned_part, str):
        if case_insensitive:
            banned_part = banned_part.lower()
            needle = needle.lower()
        return banned_part in needle
    elif isinstance(banned_part, re.Pattern):
        return bool(banned_part.search(needle))
    return False


def remove_banned_pictures(limit=100, dry_run=False):
    qs = Picture.objects.select_related("card").order_by("-created")[:limit]

    patterns: list[tuple[int, str, bool, bool]] = []
    patterns_qs = (
        BannedUrlPattern.objects.filter(
            modified__gte=timezone.now() - datetime.timedelta(days=30)
        )
        .order_by("-modified")
        .values("id", "pattern", "is_regex", "case_insensitive")
    )
    for pattern in patterns_qs:
        patterns.append(
            (
                pattern["id"],
                pattern["pattern"],
                pattern["is_regex"],
                pattern["case_insensitive"],
            )
        )

    for picture in qs:
        needles = [picture.img]
        if picture.mp4src:
            needles.append(picture.mp4src)

        for id, pattern, is_regex, case_insensitive in patterns:
            if is_regex:
                banned_part = re.compile(
                    pattern, re.IGNORECASE if case_insensitive else 0
                )
            else:
                banned_part = pattern
            if any(
                _is_banned(banned_part, needle, case_insensitive=case_insensitive)
                for needle in needles
            ):
                print("SKIP THIS PICTURE!!!!")
                print(picture)
                print("banned_part:", pattern)
                if not dry_run:
                    picture.delete()
                    BannedUrlPattern.objects.filter(id=id).update(kills=F("kills") + 1)
                    break


@periodic_task(crontab(hour="*", minute="10"))
def remove_banned_pictures_periodically():
    remove_banned_pictures()


@periodic_task(crontab(minute="20"))
def delete_old_image_proxy_files():
    _delete_old_image_proxy_files()


def _delete_old_image_proxy_files():
    cache_root = settings.IMAGE_PROXY_CACHE_ROOT
    if not cache_root.exists():
        print(f"WARNING {cache_root} does not exist")
        return

    count = 0
    MAX_COUNT = 20
    MIN_AGE_DAYS = 100

    for file_path in cache_root.rglob("*"):
        if file_path.is_file():
            age_seconds = time.time() - file_path.stat().st_mtime
            age_hours = age_seconds / 3600
            age_days = age_hours / 24

            deleted = False
            if age_days > MIN_AGE_DAYS:
                print(
                    f"Deleting old image proxy file: {file_path}, "
                    f"Age: {age_days:.1f} days"
                )
                file_path.unlink()
                deleted = True
                count += 1
            elif file_path.stat().st_size == 0:
                print(f"Deleting empty image proxy file: {file_path}")
                file_path.unlink()
                deleted = True
                count += 1

            if deleted:
                count_files_in_dir = len(list(file_path.parent.glob("*")))
                if not count_files_in_dir:
                    print("No more files in this directory")
                    file_path.parent.rmdir()

        if count >= MAX_COUNT:
            break


@periodic_task(crontab(minute="25"))
def delete_old_banned_url_patterns():
    BannedUrlPattern.objects.filter(
        modified__lt=timezone.now() - datetime.timedelta(days=100)
    ).delete()


@task()
def preload_image_proxies_task(card_id: int, sleep_delay: float = 1):
    print("Preloading image proxies for", repr(card_id))
    card = Card.objects.get(id=card_id)
    load_all_image_proxies(card, sleep_delay=sleep_delay)


@periodic_task(crontab(minute="55"))
def delete_old_cards(dry_run=False):
    DAYS = 600
    qs = Card.objects.filter(created__lt=timezone.now() - datetime.timedelta(days=DAYS))
    print("CHIVEPROXY CARDS", qs.count(), "ARE OLDER THAN", DAYS, "DAYS")
    if not dry_run:
        qs.delete()


@periodic_task(crontab(minute="*/5"))
def start_image_transcription():
    then = timezone.now() - timezone.timedelta(days=2)
    pictures = Picture.objects.filter(
        created__gte=then,
        transcript__isnull=True,
        image_proxy_conversions__img__isnull=False,
        transcript_error__isnull=True,
        # because won't be looking at the img anyway if it as a video or gif
        mp4src__isnull=True,
        gifsrc__isnull=True,
    )
    print(
        f"Starting image transcription task {timezone.now()}: "
        f"{pictures.count()} pictures to process"
    )

    max_count = 10
    count = 0

    count_success = 0
    count_failure = 0
    count_progress = 0
    in_progress: list[int] = []
    count_progress_success = 0
    count_skipped = 0
    for picture in pictures[: max_count * 10]:
        fp = settings.IMAGE_PROXY_CACHE_ROOT / picture.image_proxy_conversions["img"]
        if not fp.exists():
            print(f"Image proxy file does not exist: {fp}")
            count_skipped += 1
            continue

        llm_call = get_image_transcript(fp)
        print("LLM call result:", llm_call)
        if llm_call.status == "success":
            count_success += 1
            transcript = ""
            for row in llm_call.response["content"]:
                if row["type"] == "text":
                    transcript = row["text"].strip()
            picture.transcript = transcript
            picture.save()
        elif llm_call.status == "progress":
            count_progress += 1
            in_progress.append(picture.id)
            count += 1
            time.sleep(1)
        else:
            picture.transcript_error = str(llm_call.error)
            picture.save()
            count_failure += 1
            print(f"LLM call failed for {fp}: {llm_call}")

        if count >= max_count:
            break

    if in_progress:
        print(f"Going to check back on {len(in_progress)} in progress calls")
        time.sleep(5)

        pictures = Picture.objects.filter(id__in=in_progress)
        for picture in pictures:
            fp = (
                settings.IMAGE_PROXY_CACHE_ROOT / picture.image_proxy_conversions["img"]
            )
            llm_call = get_image_transcript(fp)
            print("LLM call result:", llm_call)
            if llm_call.status == "success":
                transcript = ""
                for row in llm_call.response["content"]:
                    if row["type"] == "text":
                        transcript = row["text"].strip()
                picture.transcript = transcript
                picture.save()
                count_progress_success += 1
            elif llm_call.status == "error":
                picture.transcript_error = str(llm_call.error)
                picture.save()

    print(
        "start_image_transcription: "
        f"{count_success=} {count_failure=} {count_progress=} "
        f"{count_progress_success=} {count_skipped=}"
    )
