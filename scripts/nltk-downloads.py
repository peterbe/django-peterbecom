# Run this script to download the necessary NLTK data files
import nltk

for info_or_id in ("wordnet", "punkt", "punkt_tab", "stopwords"):
    if not nltk.download(info_or_id):
        raise Exception(f"Unable to download NLTK data file: {info_or_id!r}.")
