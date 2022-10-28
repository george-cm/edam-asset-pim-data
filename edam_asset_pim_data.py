"""This script aims to get information about eDAM digital assets' PIM item and product assignments.
The olny dependency is Python >= 3.10 and the Python standard library"""

import csv
import json
import sys
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError
from urllib.request import urlopen


def main():
    """Main entry point of the program"""

    in_file = Path("PDF_documents_received_as_images_Sheet1.csv")
    url_column_name = "p_internalurl"

    if not in_file.exists():
        sys.exit("The input file does not exist")

    encoding = "utf-8"
    with in_file.open("rb") as in_fb:
        magic_bytes = in_fb.read(3)
        if b"eDA" == magic_bytes:
            # we are in Excel CSV territory which encodes CSV files with UTF with BOM (byte order mark)
            # which means the first 3 bytes are \xEF \xBB \xBF = b'eDA'
            encoding = "utf-8-sig"

    out_file = in_file.with_name(in_file.stem + "_pim-assignments.csv")

    with in_file.open("r", encoding=encoding) as inf, out_file.open("w", encoding=encoding, newline="") as outf:
        reader = csv.DictReader(inf, dialect="excel")
        header = ["PIM Product no.", "PIM Item no."] + reader.fieldnames  # type: ignore
        writer = csv.DictWriter(outf, dialect="excel", fieldnames=header)  # type: ignore
        writer.writeheader()
        found_url_column = True

        for line in reader:
            if not url_column_name in line:
                found_url_column = False
                break

            url = line[url_column_name]
            if not url:
                continue

            print(f"Downloading: {url}")
            asset_data = download_asset_json(url)
            if not asset_data:
                print(f"Download failed: {url}")
                continue

            print("Processing...")
            pim_data = get_pim_product_and_item_assigments(asset_data)
            if pim_data["products"] or pim_data["items"]:
                for product in pim_data["products"]:
                    row = {"PIM Product no.": product, "PIM Item no.": None, **line}
                    writer.writerow(row)
                for item in pim_data["items"]:
                    row = {"PIM Product no.": None, "PIM Item no.": item, **line}
                    writer.writerow(row)
            else:
                row = {
                    "PIM Product no.": "NOT ASSIGNED TO ANY PRODUCTS",
                    "PIM Item no.": "NOT ASSIGNED TO ANY ITEMS",
                    **line,
                }

    if not found_url_column:
        out_file.unlink(missing_ok=True)
        sys.exit(f"The column '{url_column_name}' is not present in the input CSV file.")


def get_pim_product_and_item_assigments(asset_data: Optional[dict]) -> dict[str, list[str]]:
    """Gets a dict with asset data and returns a dict with pim "products" list and
    "items" list to which the asset was assigned.
    If products are missing it returns an empyt list. The same for items."""

    items = []
    products = []
    match asset_data:
        case {"jcr:content": {"metadata": {**metadata}}}:
            match metadata:
                case {"edam:item-to-pim": str(items_string)}:
                    items = list(map(str.strip, items_string.split(",")))

            match metadata:
                case {"edam:product-to-pim": str(products_string)}:
                    products = list(map(str.strip, products_string.split(",")))
    return {"products": products, "items": items}


def download_asset_json(url: str) -> Optional[dict]:
    """Gets a url of an AEM DAM digital asset and returns a dict of its json representation."""

    try:
        with urlopen(url.strip() + ".2.json", timeout=300) as res:
            if res.status < 400:
                return json.loads(res.read().decode("utf-8"))
            return None
    except HTTPError as http_error:
        print(f"Failed to get {http_error.url}. Status Code: {http_error.status} - {http_error.reason}")
        return None


if __name__ == "__main__":
    import timeit
    from datetime import timedelta

    print(str(timedelta(seconds=timeit.timeit(main, number=1))))
    # main()
