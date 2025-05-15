from pathlib import Path
from time import time
from typing import Literal

import ffmpeg

EXTENSIONS = {"mov": ".mov", "mp4": ".mp4", "webm": ".webm"}
MIME_TYPES = {"mov": "video/mov", "mp4": "video/mp4", "webm": "video/webm"}


def process_blog_video_to_cache(
    video_file: Path, oid: str, video_type: Literal["mov", "mp4", "webm"]
):
    root = Path("cache") / "plog" / oid
    extension = EXTENSIONS[video_type]
    mime_type = MIME_TYPES[video_type]
    destination = root / video_file.name.replace(video_file.suffix, extension)
    if not destination.exists():
        t0 = time()
        destination.parent.mkdir(exist_ok=True, parents=True)
        ffmpeg.input(str(video_file)).output(str(destination)).run()
        t1 = time()
        print(f"---- Took {t1 - t0:.1f} seconds to generate {destination} ----")
    return {"url": f"/{destination}", "type": mime_type}


def process_video_to_image(video_file: Path, format="jpg", ss=0, width=1500):
    image_file = video_file.parent / video_file.name.replace(
        video_file.suffix, f"_{ss}.{format}"
    )

    if not image_file.exists():
        t0 = time()
        (
            ffmpeg.input(str(video_file), ss=ss)
            .filter("scale", width, -1)
            .output(str(image_file), vframes=1)
            .run()
        )
        t1 = time()
        print(
            f"Took {t1 - t0:.1f} seconds to convert {video_file.name} to {image_file.name}"
        )
    return image_file
