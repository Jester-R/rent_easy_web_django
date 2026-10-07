#!/usr/bin/env python
"""Idempotently re-apply the django-bolt _iter_field_defaults fix in the venv.

django-bolt's upstream _iter_field_defaults right-aligns __struct_defaults__
against the field list, which mislabels interleaved required/defaulted fields.
The patched version reports per-field defaults via msgspec.structs.fields, so
RentEasy serializers keep working for models where required and defaulted
fields are interleaved.

Safe to run repeatedly: no-ops once the fix is present. django-bolt must be
installed (bootstrap creates the venv and installs deps first).
"""

from __future__ import annotations

import pathlib
import re
import sys

NEW_FUNC = '''def _iter_field_defaults(cls: type) -> list[tuple[str, Any]]:
    """
    Iterate over (field_name, default_value) pairs for a msgspec.Struct class.

    Uses ``msgspec.structs.fields`` so defaults are reported per-field.  This is
    correct for kw_only structs (which Serializer enforces): ``__struct_defaults__``
    is a compact tuple that does not right-align with the field list when
    required and defaulted fields are interleaved, so end-alignment math would
    mislabel required fields as having defaults.

    Args:
        cls: A msgspec.Struct subclass

    Returns:
        List of (field_name, default_value) tuples
    """
    result = []
    try:
        field_infos = msgspec_structs.fields(cls)
    except Exception:
        field_infos = ()
    for field_info in field_infos:
        if not field_info.required:
            result.append((field_info.name, field_info.default))
    return result
'''

MARKER = "msgspec_structs.fields(cls)"


def main() -> None:
    try:
        import django_bolt.serializers.base as base
    except ImportError as exc:
        sys.exit(f"django_bolt not installed yet; nothing to patch ({exc})")

    path = pathlib.Path(base.__file__)
    text = path.read_text(encoding="utf-8")

    if MARKER in text:
        print("django-bolt already patched; nothing to do")
        return

    pattern = re.compile(r"(?m)^def _iter_field_defaults\(cls: type\).*?(?=\ndef )", re.DOTALL)
    match = pattern.search(text)
    if not match:
        sys.exit("could not locate _iter_field_defaults; not patching")

    path.write_text(text[: match.start()] + NEW_FUNC + "\n" + text[match.end() :], encoding="utf-8")
    print(f"patched {path}")


if __name__ == "__main__":
    main()