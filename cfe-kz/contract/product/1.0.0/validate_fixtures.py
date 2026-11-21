# -*- coding: utf-8 -*-
"""Проверяет fixtures контракта номенклатуры 1.0.0 и, с аргументом --live <json>, живые сообщения products."""

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parent
ALLOWED_CODES = (
    "REQUIRED_FIELD_MISSING",
    "INVALID_FORMAT",
    "UNSUPPORTED_VERSION",
    "REFERENCE_NOT_FOUND",
    "DUPLICATE_CONFLICT",
    "INTERNAL_ERROR",
)
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
SENDER_1C = frozenset({"1c-rf", "1c-kz"})


def load_json(path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def pointer(absolute_path):
    result = ""
    for part in absolute_path:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += (("." if result else "") + str(part))
    return result


def classify(error):
    path = pointer(error.absolute_path)
    if error.validator == "required":
        match = re.search(r"'([^']+)' is a required property", error.message)
        field = match.group(1) if match else ""
        full_path = f"{path}.{field}" if path else field
        return "REQUIRED_FIELD_MISSING", full_path
    if error.validator == "anyOf" and (
        path.startswith("contracts[") or path.startswith("bank_accounts[")
    ):
        return "REQUIRED_FIELD_MISSING", path
    if path == "name" and error.validator in ("pattern", "minLength"):
        return "REQUIRED_FIELD_MISSING", path
    if path == "name" and error.validator == "type" and error.instance is None:
        return "REQUIRED_FIELD_MISSING", path
    return "INVALID_FORMAT", path


def is_null_alternative(error):
    return error.validator == "type" and error.validator_value == "null"


def walk_error(error):
    if error.validator in ("anyOf", "oneOf") and error.context:
        useful = [item for item in error.context if not is_null_alternative(item)]
        required_sets = [
            set(item.validator_value)
            for item in useful
            if item.validator == "required"
        ]
        if required_sets == [{"id"}, {"uid"}] or required_sets == [{"uid"}, {"id"}]:
            path = pointer(error.absolute_path)
            if not path:
                return [("REQUIRED_FIELD_MISSING", "id")]
            return [("REQUIRED_FIELD_MISSING", path)]
        nested = []
        for item in useful:
            nested.extend(walk_error(item))
        if nested:
            return nested
    return [classify(error)]


def meaningful_errors(validator, instance):
    found = []
    for error in validator.iter_errors(instance):
        found.extend(walk_error(error))
    return sorted(set(found))


def sender_body_errors(headers, value):
    """У номенклатуры id не обязателен ни для одного отправителя; uid обязателен схемой тела."""
    return []


def expected_pairs(document):
    pairs = []
    for item in document.get("expectedErrors", []):
        pairs.append((item["code"], item["path"]))
    return sorted(pairs)


def check_catalog():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = [code for code in ALLOWED_CODES if f"`{code}`" not in readme]
    if missing:
        raise SystemExit("В README нет кодов: " + ", ".join(missing))
    if "Путь JSON" not in readme:
        raise SystemExit("В README не описаны правила пути")


def main():
    check_catalog()
    headers_schema = load_json(ROOT / "headers.schema.json")
    body_schema = load_json(ROOT / "body.schema.json")
    try:
        Draft202012Validator.check_schema(headers_schema)
        Draft202012Validator.check_schema(body_schema)
    except SchemaError as error:
        raise SystemExit(f"Схема некорректна: {error.message}") from error
    headers_validator = Draft202012Validator(headers_schema)
    body_validator = Draft202012Validator(body_schema)

    failures = []
    checked = 0
    for path in sorted((ROOT / "fixtures").rglob("*.json")):
        document = load_json(path)
        checked += 1
        actual = meaningful_errors(headers_validator, document["headers"])
        actual.extend(meaningful_errors(body_validator, document["value"]))
        actual.extend(sender_body_errors(document["headers"], document["value"]))
        actual = sorted(set(actual))
        if "expectedErrors" in document:
            expected = expected_pairs(document)
            unknown = [code for code, _ in expected if code not in ALLOWED_CODES]
            if unknown or actual != expected:
                failures.append((path.name, expected, actual, unknown))
        elif actual:
            failures.append((path.name, [], actual, []))

    if failures:
        for name, expected, actual, unknown in failures:
            print(name)
            print("  expected:", expected)
            print("  actual:  ", actual)
            if unknown:
                print("  unknown: ", unknown)
        raise SystemExit(f"Не прошли fixtures: {len(failures)} из {checked}")
    print(f"OK: {checked} fixtures")
    if len(sys.argv) > 2 and sys.argv[1] == "--live":
        live = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        bad = 0
        for item in live:
            errs = meaningful_errors(headers_validator, item["headers"])
            errs.extend(meaningful_errors(body_validator, json.loads(item["value"])))
            if errs:
                bad += 1
                print("live offset", item.get("offset"), errs)
        print(f"LIVE: {len(live) - bad} of {len(live)} messages pass")
        if bad:
            raise SystemExit(1)


if __name__ == "__main__":
    sys.exit(main())
