import sys
import os
from unittest.mock import MagicMock, patch

# Add the backend directory to sys.path
sys.path.append(os.getcwd())


def test_user_timeline_pagination():
    print("Testing UserController.get_user_timeline pagination...")
    from app.controllers.user_controller import UserController

    # Mock DB Session
    mock_db = MagicMock()

    # Mocking the query chain: db.query().filter().order_by().offset().limit().all()
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_order_by = mock_filter.order_by.return_value
    mock_offset = mock_order_by.offset.return_value
    mock_limit = mock_offset.limit.return_value
    mock_limit.all.return_value = []  # Return empty list for successful chain

    # Mock the UserMetadata resolution
    with patch("app.controllers.user_controller.UserMetadata") as mock_user_metadata:
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            service_id="test_id"
        )

        # Call with limit=5, offset=10
        UserController.get_user_timeline(mock_db, "test_user", limit=5, offset=10)

        # Verify offset and limit were called with correct values
        # The chain in UserController is db.query(UserTimelineLedger).filter(...).order_by(...).offset(offset).limit(limit).all()
        mock_order_by.offset.assert_called_once_with(10)
        mock_offset.limit.assert_called_once_with(5)

    print("UserController pagination test passed!")


def test_group_timeline_pagination():
    print("\nTesting GroupController.get_group_timeline pagination...")
    from app.controllers.group_controller import GroupController

    # Mock DB Session
    mock_db = MagicMock()

    # Mocking the query chain
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_order_by = mock_filter.order_by.return_value
    mock_offset = mock_order_by.offset.return_value
    mock_limit = mock_offset.limit.return_value
    mock_limit.all.return_value = []

    # Mock GroupMetadata resolution
    with patch("app.controllers.group_controller.GroupMetadata") as mock_group_metadata:
        # Mock group identification
        mock_group = MagicMock(id=1)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_group

        # Call with limit=2, offset=4
        GroupController.get_group_timeline(mock_db, "test_group", limit=2, offset=4)

        # Verify offset and limit
        mock_order_by.offset.assert_called_once_with(4)
        mock_offset.limit.assert_called_once_with(2)

    print("GroupController pagination test passed!")


if __name__ == "__main__":
    try:
        test_user_timeline_pagination()
        test_group_timeline_pagination()
        print("\nAll logic verification tests passed successfully!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
