from huey.contrib.djhuey import task

from peterbecom.publicapi.views.lyrics_utils import get_song


@task()
def populate_song_cache_by_id(id: int) -> None:
    assert isinstance(id, int), "id must be an int"

    try:
        res = get_song(id, retries=0)
        print("Successfully populated song cache for id", id, "->", res["song"]["name"])
    except Exception as e:
        print("Failed to populate song cache for id", id, "->", str(e))
