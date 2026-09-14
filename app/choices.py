"""Stored values are independent from their Japanese display labels."""

ADL_CHOICES = {"normal": "正常", **{v: v for v in ("J1", "J2", "A1", "A2", "B1", "B2", "C1", "C2")}}
DEMENTIA_CHOICES = {"normal": "正常", **{v: v for v in ("I", "IIa", "IIb", "IIIa", "IIIb", "IV", "M")}}
CARE_CHOICES = {
    "support_1": "要支援1", "support_2": "要支援2",
    **{f"care_{n}": f"要介護{n}" for n in range(1, 6)},
}

SELECT_CHOICES = {
    "adl_independence_level": ADL_CHOICES,
    "dementia_independence_level": DEMENTIA_CHOICES,
    "care_level": CARE_CHOICES,
}
