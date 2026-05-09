from math import isnan


def is_empty_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        try:
            return isnan(value)
        except TypeError:
            return False
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "null"}


def normalize_text(value: object) -> str | None:
    if is_empty_value(value):
        return None
    text = str(value).strip()
    return " ".join(text.split())
