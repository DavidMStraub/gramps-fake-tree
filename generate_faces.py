"""Download images from thispersondoesnotexist.com."""

import argparse
import io
import os

import requests
from PIL import Image

URL = "https://thispersondoesnotexist.com"
HEADERS = {"User-Agent": "Gramps Faker 1.0"}


def process_response(filename: str, content: bytes, to_grayscale: bool = False):
    image = Image.open(io.BytesIO(content))
    if to_grayscale:
        image = image.convert("L")
    image.save(f"{filename}.jpg")


def main():
    parser = argparse.ArgumentParser(description="Download random faces.")
    parser.add_argument("num", help="Number of faces", type=int)
    args = parser.parse_args()

    os.makedirs("images/people/color", exist_ok=True)
    os.makedirs("images/people/grayscale", exist_ok=True)

    for i in range(args.num):
        content = requests.get(URL, headers=HEADERS).content
        process_response(f"images/people/color/{i + 1:05}", content, to_grayscale=False)
        content = requests.get(URL, headers=HEADERS).content
        process_response(
            f"images/people/grayscale/{i + 1:05}", content, to_grayscale=True
        )


if __name__ == "__main__":
    main()
