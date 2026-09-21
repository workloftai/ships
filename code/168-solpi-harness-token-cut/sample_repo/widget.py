def apply_discount(price, pct):
    # regression: should divide by 100, refactor dropped it
    return price - price * pct
def line_total(qty, price, pct):
    return qty * apply_discount(price, pct)
