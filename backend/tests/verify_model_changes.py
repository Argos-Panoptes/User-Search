from app.schemas.api_models import UserSearchRequest, GroupSearchRequest
from pydantic import ValidationError


def test_user_search_request():
    print("Testing UserSearchRequest...")
    try:
        req = UserSearchRequest(limit=10, offset=5)
        if req.limit == 10 and req.offset == 5:
            print("PASS: UserSearchRequest accepted 'limit' and 'offset'")
        else:
            print(
                f"FAIL: UserSearchRequest values mismatch: limit={req.limit}, offset={req.offset}"
            )
    except ValidationError as e:
        print(f"FAIL: UserSearchRequest rejected 'limit' or 'offset': {e}")
    except Exception as e:
        print(f"FAIL: Unexpected error: {e}")


def test_group_search_request():
    print("\nTesting GroupSearchRequest...")
    try:
        req = GroupSearchRequest(limit=10, offset=5)
        if req.limit == 10 and req.offset == 5:
            print("PASS: GroupSearchRequest accepted 'limit' and 'offset'")
        else:
            print(
                f"FAIL: GroupSearchRequest values mismatch: limit={req.limit}, offset={req.offset}"
            )
    except ValidationError as e:
        print(f"FAIL: GroupSearchRequest rejected 'limit' or 'offset': {e}")
    except Exception as e:
        print(f"FAIL: Unexpected error: {e}")


if __name__ == "__main__":
    test_user_search_request()
    test_group_search_request()
