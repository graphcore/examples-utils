# Copyright (c) 2023 Graphcore Ltd. All rights reserved.
import json
import requests

from time import sleep


API_URL = "https://api.short.io/api"
API_URL_V2 = "https://api-v2.short.cm/statistics/link/"
DOMAIN_ID = 661395
SESSION = requests.Session()
MAPPING_PATH = "./linkpath_to_names.json"


HEADERS = {
    "accept": "application/json",
    "Authorization": "sk_Yz6hYdI2bfKtr2rG",
}


def get_all_link_ids(domain_id: int) -> list:
    """Get all links and metadata for a given domain ID."""

    response = SESSION.get(
        f"{API_URL}/links?domain_id={domain_id}",
        headers=HEADERS,
    )
    response = json.loads(response.text)

    links = []
    for link_metadata in response["links"]:
        links.append(link_metadata["id"])

    return links


def open_mapping_file(mapping_path: str) -> dict:
    """Open the mapping file and return the contents as a dictionary."""

    with open(mapping_path, "r") as mapping_file:
        mapping = json.load(mapping_file)

    return mapping


def get_notebook_names(link_ids: list) -> list:
    """Extract the notebook name from the URL ID"""

    mapping = open_mapping_file(MAPPING_PATH)

    link_names = {}
    for id in link_ids:
        if id in mapping.keys():
            name = mapping[id]
            link_names[id] = {"notebook_name": name}

    return link_names


def get_num_clicks(link_ids: list) -> list:
    """Get the number of clicks for each URL."""

    link_counts = {}
    for id in link_ids:
        url = f"{API_URL_V2}{id}?period=total&tzOffset=0"
        response = SESSION.get(url, headers=HEADERS).json()

        link_counts[id] = {
            "total": response["totalClicks"],
            "human": response["humanClicks"],
        }

        sleep(1)

    return link_counts


def merge_link_dicts(link_names: dict, link_counts: dict) -> dict:
    """Merge the link names and counts dictionaries."""

    link_statistics = {}
    for id in link_names.keys():

        if id not in link_counts.keys():
            raise ValueError(f"Link ID {id} not found in link_counts dictionary.")

        link_statistics[link_names[id]["notebook_name"]] = {
            "total": link_counts[id]["total"],
            "human": link_counts[id]["human"],
        }

    return link_statistics


if __name__ == "__main__":

    link_ids = get_all_link_ids(DOMAIN_ID)

    link_names = get_notebook_names(link_ids)
    link_counts = get_num_clicks(link_ids)

    link_statistics = merge_link_dicts(link_names, link_counts)

    print(link_statistics)
