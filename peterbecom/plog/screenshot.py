import re

import subprocess

from django.conf import settings


def get_image_url(url, width=1280, height=1000):

    proc = subprocess.Popen("./screenshot.js", url)
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )

    img_tag = cloudinary.CloudinaryImage(url, type="url2png").image(
        crop="fill", width=width, height=height, gravity="north", sign_url=sign_url
    )

    url = re.findall('src="([^"]+)"', img_tag)[0]
    url = url.replace("http://", "https://")

    return url
