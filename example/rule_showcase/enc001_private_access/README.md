# ENC001 — `forbid_private_access` showcase

The reference package has an `Inventory` class that keeps its stock in the
private `_stock` and hands out a copy through `items()`, and a `shop.report`
function that must read the stock through that method — never as
`inventory._stock`. The check is static: it reads the code of `report` and
runs nothing.

```bash
python-arch-test --source example/rule_showcase/enc001_private_access/reference \
    --targets-dir example/rule_showcase/enc001_private_access/assignments \
    --format json
```

## Marker matrix exercised

| Reference entity | Marker                    | What it enforces                                                    |
|------------------|---------------------------|---------------------------------------------------------------------|
| `shop:report`    | `forbid_private_access()` | `report` reads no attribute starting with `_` of another object     |

## Target index

| Target                       | Expected | What it isolates                                                         |
|------------------------------|----------|--------------------------------------------------------------------------|
| `target_pass_basic`          | PASS     | Reads the stock through `items()`, as the reference does                 |
| `target_pass_eq_same_class`  | PASS     | Compares through `==`: `other._stock` is read inside `Inventory.__eq__`  |
| `target_fail_reads_private`  | FAIL     | `inventory._stock.items()` straight from `report`                        |

Targets do not carry `__archtest__` metadata; the markers live only on the
reference side.

See `findings.md` for the expected vs observed verdicts.
