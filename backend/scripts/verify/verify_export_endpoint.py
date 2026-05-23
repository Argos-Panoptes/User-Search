import sys
import os
import csv
import io

# Add project root to path
sys.path.append(os.getcwd())

from fastapi.testclient import TestClient
from app.main import app  # assuming app is initialized in app.main


def test_export():
    client = TestClient(app)

    # Test param combination
    params = {"limit": 10, "q": "Test"}

    response = client.get(
        "/api/v1/users/export", params=params
    )  # Assuming prefix /api/v1

    if response.status_code != 200:
        print(f"FAILED: Status Code {response.status_code}")
        print(response.text)
        return

    if "text/csv" not in response.headers["content-type"]:
        print(f"FAILED: Content-Type {response.headers['content-type']}")
        return

    content = response.text

    # Parse CSV
    f = io.StringIO(content)
    reader = csv.reader(f)
    try:
        headers = next(reader)
    except StopIteration:
        print("FAILED: Empty CSV")
        return

    expected_headers = [
        "Service ID",
        "Profile Name",
        "Name",
        "Profile Full Name",
        "Username",
        "Phone",
        "Is Admin",
        "Group Count",
        "Admin Group Count",
        "About",
        "Groups",
        "Export Timestamp",
        "Avatar URL",
    ]

    if headers == expected_headers:
        print("SUCCESS: Headers match expected format.")
        print(f"Found {len(headers)} columns.")
    else:
        print(f"FAILED: Headers mismatch.")
        print(f"Expected: {expected_headers}")
        print(f"Got:      {headers}")

        # specific diff
        set_exp = set(expected_headers)
        set_got = set(headers)
        missing = set_exp - set_got
        extra = set_got - set_exp
        if missing:
            print(f"Missing: {missing}")
        if extra:
            print(f"Extra: {extra}")


if __name__ == "__main__":
    # Check if we can import app
    try:
        from app.main import app

        test_export()
    except ImportError:
        print("Could not import app.main. Please verify path.")
