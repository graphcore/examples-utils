# Copyright (c) 2023 Graphcore Ltd. All rights reserved.import requests


def get_final_url(short_url):
    """
    This function takes a shortened URL as input and returns the final, true URL.
    """
    try:
        response = requests.get(short_url, timeout=10)  # Add a timeout for the request
        response.raise_for_status()  # Raise an exception if the GET request was unsuccessful
    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error: {errh}")
        return None
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
        return None
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
        return None
    except requests.exceptions.RequestException as err:
        print(f"An error occurred: {err}")
        return None

    return response.url


short_url = "https://ipu.dev/mLDgSt"  # Replace with your actual short URL
print(get_final_url(short_url))
