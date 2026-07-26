# Run this script to download the necessary NLTK data files
import nltk


class DownloadError(Exception):
    pass


for info_or_id in ("wordnet", "punkt", "punkt_tab", "stopwords"):
    if not nltk.download(info_or_id):
        raise DownloadError(f"Unable to download NLTK data file: {info_or_id!r}.")
