from app.controllers.auth_controller import AuthController
from app.schemas.auth_models import UserResponse, PaymentTransactionResponse
import datetime


# Mock classes to simulate SQLAlchemy models
class MockPaymentTransaction:
    def __init__(self, id, amount, currency, status, event_type):
        self.id = id
        self.amount = amount
        self.currency = currency
        self.status = status
        self.event_type = event_type
        self.created_at = datetime.datetime.now()


class MockAppUser:
    def __init__(self, transactions):
        self.id = 1
        self.email = "test@example.com"
        self.full_name = "Test User"
        self.picture = None
        self.is_active = True
        self.is_superuser = False
        self.last_login = None
        self.subscription = None
        self.payment_transactions = transactions

    @property
    def total_spent(self) -> float:
        if not self.payment_transactions:
            return 0.0
        return float(
            sum(
                t.amount
                for t in self.payment_transactions
                if t.status == "succeeded"
                and t.event_type == "invoice_payment"
                and t.amount is not None
            )
        )

    @property
    def total_payments(self) -> int:
        if not self.payment_transactions:
            return 0
        return len(
            [
                t
                for t in self.payment_transactions
                if t.status == "succeeded" and t.event_type == "invoice_payment"
            ]
        )


def test_billing_filter():
    # Setup transactions
    t1 = MockPaymentTransaction(
        1, 10.0, "usd", "succeeded", "invoice_payment"
    )  # Should keep
    t2 = MockPaymentTransaction(
        2, 10.0, "usd", "succeeded", "invoice.payment_succeeded"
    )  # Should filter
    t3 = MockPaymentTransaction(
        3, 10.0, "usd", "failed", "invoice.payment_failed"
    )  # Should keep
    t4 = MockPaymentTransaction(
        4, 0.0, "usd", "succeeded", "checkout.session.completed"
    )  # Should filter

    user = MockAppUser([t1, t2, t3, t4])

    print(f"Total Spent (Computed): {user.total_spent}")  # Should be 10.0 (t1 only)
    print(f"Total Payments (Computed): {user.total_payments}")  # Should be 1 (t1 only)

    # Convert via Controller
    response = AuthController.get_me(user)

    print(f"Response Total Spent: {response.total_spent}")
    print(f"Response Total Payments: {response.total_payments}")

    print("Filtered Transactions:")
    for t in response.payment_transactions:
        print(f"- {t.event_type} ({t.status})")

    # Assertions
    assert len(response.payment_transactions) == 2
    event_types = [t.event_type for t in response.payment_transactions]
    assert "invoice_payment" in event_types
    assert "invoice.payment_failed" in event_types
    assert "invoice.payment_succeeded" not in event_types
    assert response.total_spent == 10.0
    assert response.total_payments == 1

    print("\nTest PASSED!")


if __name__ == "__main__":
    test_billing_filter()
