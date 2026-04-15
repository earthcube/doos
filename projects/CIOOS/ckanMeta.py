import requests
from pprint import pprint

def get_ckan_metadata(dataset_id: str):
    url = f"https://catalogue.cioos.ca/api/3/action/package_show?id={dataset_id}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data["success"]:
        pkg = data["result"]
        print("Title:", pkg["title"])
        print("EOVs:", pkg.get("eov"))
        print("Spatial:", pkg.get("spatial") or "No GeoJSON")
        print("Resources count:", len(pkg.get("resources", [])))
        print("\nFull keys:", list(pkg.keys()))  # schema overview
        # pprint(pkg)  # uncomment for full dump (large!)
        return pkg
    return None

# Example usage
if __name__ == "__main__":
    get_ckan_metadata("10-25976-4y34-rn27")
