# Policies

`Policy`s encapsulate complex or cross-cutting business rules that do not belong to a single entity or action.

## Examples
*   **Discount Calculation**: Complex logic to determine the applicable discount.
*   **Approval**: Rules to determine if a document can be approved.
*   **Access**: Domain rules for who can do what (distinct from technical authorization).

## Example

```python
# src/application/policy/discount.py

def calculate_discount(user, cart_total):
    if user['is_vip']:
        return cart_total * 0.20
    if cart_total > 100:
        return cart_total * 0.10
    return 0
```
