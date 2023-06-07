# Copyright (c) 2023 Graphcore Ltd. All rights reserved.import json
import requests


API_URL = "https://api.short.io/api"
API_URL_V2 = "https://api-v2.short.cm/statistics/link/"
API_KEY = "sk_Yz6hYdI2bfKtr2rG"
DOMAIN_ID = 661395
SESSION = requests.Session()


HEADERS = {
    "accept": "application/json",
    "Authorization": API_KEY,
}


def get_all_links(domain_id: int) -> list:
    """Get all links and metadata for a given domain ID."""

    response = SESSION.get(
        f"{API_URL}/links?domain_id={DOMAIN_ID}",
        headers=HEADERS,
    )
    response = json.loads(response.text)

    links = []
    for link_metadata in response["links"]:
        links.append(link_metadata["shortURL"])

    return links


def get_url_ids(link_metadatas: list) -> list:
    """Get URL IDs from the link metadata."""

    url_ids = []
    for metadata in link_metadatas:
        url_ids.append(metadata["id"])

    return url_ids


def get_notebook_names(url_ids: str) -> list:
    """Extract the notebook name from the URL ID"""

    with open(mapping_path, "r") as mapping_file:
        mapping = json.load(mapping_file)

    link_names = {}
    for id in url_ids:
        name = mapping[path]

        if name not in link_names:
            link_names[name] = {"URL IDs": [id]}
        else:
            link_names[name]["URL IDs"].append(id)

    return link_names


def get_number_of_clicks():

    import requests

    url = f"{API_URL_V2}{url_id}?period=total&tzOffset=0"

    response = requests.get(url, headers=HEADERS)

    print(response.text)

    return


if __name__ == "__main__":

    link_metadata = get_all_links(DOMAIN_ID)
    url_ids = get_url_ids(link_metadata)

    link_names = get_notebook_names(url_ids)
    link_counts = get_number_of_clicks(url_ids)

    # Merge dictionaries

    print(link_statistics)
