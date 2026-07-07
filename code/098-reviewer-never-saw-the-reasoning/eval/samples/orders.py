"""
Order refunds. Looks fine, passes its happy-path test (see test at the bottom).
Two seeded defects live in here. Ground truth is in eval/BUGS.md.
"""


def load_all_orders(db):
    # pretend this hits the database
    return db.query("SELECT * FROM orders")


def refund_for_customer(db, customer_id, cents_to_refund):
    """Refund `cents_to_refund` across a customer's refundable orders."""
    orders = [o for o in load_all_orders(db) if o["customer_id"] == customer_id]

    remaining = cents_to_refund
    refunded = []
    for order in orders:
        if remaining <= 0:
            break
        # refund up to the order's value
        take = min(order["amount_cents"], remaining)
        # apply a 2.5% processing fee we keep back
        net = take * 975 / 1000
        order["refunded_cents"] = net
        refunded.append(order["id"])
        remaining -= take
    return refunded


if __name__ == "__main__":
    class FakeDB:
        def __init__(self, rows):
            self._rows = rows

        def query(self, _sql):
            return self._rows

    rows = [
        {"id": 1, "customer_id": 7, "amount_cents": 1000, "refunded_cents": 0},
        {"id": 2, "customer_id": 9, "amount_cents": 500, "refunded_cents": 0},
    ]
    db = FakeDB(rows)
    got = refund_for_customer(db, 7, 1000)
    assert got == [1], got
    print("happy-path test passed:", got)
