# -*- coding: utf-8 -*-
"""Проверяет fixtures контракта счёта 1.0.0: схемы JSON Schema, правило отправителя и согласованность сумм."""

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent
ALLOWED_CODES = (
    "REQUIRED_FIELD_MISSING",
    "REQUIRED_HEADER_MISSING",
    "INVALID_FORMAT",
    "UNSUPPORTED_VERSION",
    "REFERENCE_NOT_FOUND",
    "DUPLICATE_CONFLICT",
    "PERIOD_CLOSED",
    "DEPENDENCY_FAILED",
    "INTERNAL_ERROR",
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def pointer(parts):
    out = ""
    for part in parts:
        out += f"[{part}]" if isinstance(part, int) else (("." if out else "") + str(part))
    return out


def errors(validator, instance, headers=False):
    found = set()
    for error in validator.iter_errors(instance):
        path = pointer(error.absolute_path)
        if error.validator == "required":
            field = re.search(r"'([^']+)' is a required property", error.message).group(1)
            full = f"{path}.{field}" if path else field
            if full == "responsible":
                full = "responsible.uid"
            code = "REQUIRED_HEADER_MISSING" if headers and field == "organization-id" else "REQUIRED_FIELD_MISSING"
            found.add((code, full))
        elif path in ("contract", "contract.uid", "contract.id") and (
            instance.get("contract") is None
            or isinstance(instance.get("contract"), dict) and not (
                instance["contract"].get("id") or instance["contract"].get("uid")
            )
        ):
            found.add(("REQUIRED_FIELD_MISSING", "contract"))
        elif path in ("responsible", "responsible.uid") and (
            instance.get("responsible") is None
            or isinstance(instance.get("responsible"), dict) and not instance["responsible"].get("uid")
        ):
            found.add(("REQUIRED_FIELD_MISSING", "responsible.uid"))
        else:
            found.add(("INVALID_FORMAT", path))
    return found


def business(headers, value):
    found = set()
    if headers.get("sender") == "corp" and not isinstance(value.get("id"), int):
        found.add(("REQUIRED_FIELD_MISSING", "id"))
    rows = value.get("products")
    if isinstance(rows, list) and "sum" in value:
        try:
            total = sum(Decimal(str(r.get("sum"))) for r in rows)
            vat = sum(Decimal(str(r.get("sum_vat"))) for r in rows)
            doc = Decimal(str(value["sum"]))
            if abs(doc - total) > Decimal("0.01") and abs(doc - total - vat) > Decimal("0.01"):
                found.add(("INVALID_FORMAT", "sum"))
        except Exception:
            pass
    return found


def main():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = [code for code in ALLOWED_CODES if f"`{code}`" not in readme]
    if missing:
        raise SystemExit("В README нет кодов: " + ", ".join(missing))
    hv = Draft202012Validator(load(ROOT / "headers.schema.json"))
    bv = Draft202012Validator(load(ROOT / "body.schema.json"))
    pv = Draft202012Validator(load(ROOT / "body.portal.schema.json"))
    sv = Draft202012Validator(load(ROOT / "body.soft-delete.schema.json"))
    failures = []
    files = sorted((ROOT / "fixtures").rglob("*.json"))
    for path in files:
        doc = load(path)
        h, v = doc["headers"], doc["value"]
        actual = errors(hv, h, headers=True)
        if h.get("type") in ("invoice.soft_delete", "invoice_soft_delete"):
            actual |= errors(sv, v)
            if h.get("sender") == "corp" and not isinstance(v.get("id"), int):
                actual.add(("REQUIRED_FIELD_MISSING", "id"))
        else:
            actual |= errors(pv if h.get("sender") == "corp" else bv, v)
            actual |= business(h, v)
        expected = {(e["code"], e["path"]) for e in doc.get("expectedErrors", [])}
        if actual != expected:
            failures.append((path.name, sorted(expected), sorted(actual)))
    for name, exp, act in failures:
        print(name, "\n  expected:", exp, "\n  actual:  ", act)
    if failures:
        raise SystemExit(f"Не прошли fixtures: {len(failures)} из {len(files)}")
    print(f"OK: {len(files)} fixtures")


if __name__ == "__main__":
    sys.exit(main())
