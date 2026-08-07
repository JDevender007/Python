from __future__ import annotations

import json
import re

from pathlib import Path
from urllib.parse import urljoin


def clean_text(text):

    if not text:

        return ""

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def build_absolute_url(
    base_url,
    link,
):

    if not link:

        return ""

    return urljoin(
        base_url,
        link,
    )


def create_directory(path):

    Path(path).mkdir(
        parents=True,
        exist_ok=True,
    )


def save_json(
    data,
    file,
):

    with open(
        file,
        "w",
        encoding="utf-8",
    ) as output:

        json.dump(
            data,
            output,
            indent=4,
            ensure_ascii=False,
        )


def validate_url(url):

    return url.startswith(("http://", "https://"))
