from __future__ import annotations


def bmi_value(height_cm: float, weight_kg: float) -> float:
    if height_cm <= 0 or weight_kg <= 0:
        raise ValueError("Height and weight must be greater than zero.")
    height_m = height_cm / 100
    return round(weight_kg / (height_m * height_m), 1)


def bmi_category(bmi: float) -> str:
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Healthy"
    if bmi < 30:
        return "Overweight"
    return "Obese"
