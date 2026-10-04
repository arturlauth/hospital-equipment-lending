"""Brazilian document rules. Values are stored as digits only."""

import re

from django.core.exceptions import ValidationError


def only_digits(value):
    return re.sub(r"\D", "", value or "")


def cpf_check_digits(first_nine):
    """The two verifier digits of a CPF, computed from its first nine digits."""
    digits = [int(d) for d in first_nine]
    for weight_start in (10, 11):
        total = sum(d * w for d, w in zip(digits, range(weight_start, 1, -1), strict=False))
        digits.append(total * 10 % 11 % 10)
    return f"{digits[-2]}{digits[-1]}"


def validate_cpf(value):
    cpf = only_digits(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11 or cpf_check_digits(cpf[:9]) != cpf[9:]:
        raise ValidationError("CPF inválido.", code="invalid_cpf")


def validate_cep(value):
    if len(only_digits(value)) != 8:
        raise ValidationError("CEP deve ter 8 dígitos.", code="invalid_cep")
