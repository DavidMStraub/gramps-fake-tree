"""Download images from pexels.com."""

import argparse
import io
import os

import requests
from PIL import Image

API_URL = "https://api.pexels.com/v1/search"
HEADERS = {"User-Agent": "Gramps Faker 1.0"}

API_KEY = os.getenv("PEXELS_API_KEY")


def fetch_images(query: str, num: int = 100):
    """Fetch num images matching the query. Returns a generator."""
    URL = f"{API_URL}?query={query}&per_page={num}"
    headers = {"Authorization": f"{API_KEY}"}
    response = requests.get(URL, headers=headers)
    response.raise_for_status()

    data = response.json()
    for photo in data["photos"]:
        photo_url = photo["src"]["large"]
        response_photo = requests.get(photo_url)
        response_photo.raise_for_status()
        yield response_photo.content


def process_response(filename: str, content: bytes, to_grayscale: bool = False):
    image = Image.open(io.BytesIO(content))
    if to_grayscale:
        image = image.convert("L")
    image.save(f"{filename}.jpg")


def main():
    parser = argparse.ArgumentParser(description="Download random faces.")
    parser.add_argument("num", help="Number of images", type=int)
    parser.add_argument("--query", help="Query string")
    args = parser.parse_args()
    query = args.query

    if not query or " " in query:
        raise ValueError("Please provide a query and don't use spaces.")

    os.makedirs(f"images/{query}/color", exist_ok=True)
    os.makedirs(f"images/{query}/grayscale", exist_ok=True)

    for i, content in enumerate(fetch_images(query)):
        if i == args.num * 2:
            break
        use_color = i % 2 == 0
        folder = "color" if use_color else "grayscale"
        process_response(
            f"images/{query}/{folder}/{i + 1:05}", content, to_grayscale=not use_color
        )


if __name__ == "__main__":
    if not API_KEY:
        raise ValueError(
            "You need to provide the Pexels API key in the PEXELS_API_KEY"
            " environment variable."
        )

    main()
