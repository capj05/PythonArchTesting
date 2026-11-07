# ENC001 — findings

## Expected vs. observed

Without `--dynamic` (the check is static):

| Target                       | Expected | Observed                                                                                                   | Status |
|------------------------------|----------|------------------------------------------------------------------------------------------------------------|--------|
| `target_pass_basic`          | PASS     | exit=0, 1 OK                                                                                               | OK     |
| `target_pass_eq_same_class`  | PASS     | exit=0, 1 OK                                                                                               | OK     |
| `target_fail_reads_private`  | FAIL     | exit=1, 1 FAIL: `shop:report reads private attribute _stock of inventory (Inventory) at shop.py:7`         | OK     |

## Capabilities exercised

- A private read reported with the attribute, the class the parameter's
  annotation names, file and line (`details.facts`, 1:1 with the violations).
- Comparing private state belongs to the class (`Inventory.__eq__` reading
  `other._stock`); a client using `==` is not affected.

## Limitations / gotchas

- Only reads: writes (`inventory._stock = ...`, `inventory._stock[k] = v`) are
  `forbid_foreign_writes`'s, at run time.
- Access by a computed name (`getattr(inventory, "_stock")`) is not seen.
- `module._helper` on an imported module is a module's private name, which
  `module_interface` guards; it is not reported here.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
