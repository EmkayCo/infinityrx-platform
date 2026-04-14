"""Positive pay file generator for check issuance fraud prevention.

Generates a configurable CSV or fixed-width file listing all issued checks.
Delivered to the bank via SFTP or bank portal API.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class IssuedCheck:
    check_number: str
    amount: Decimal  # never float
    payee_name: str
    issue_date: date
    account_number: str
    reference: str | None = None


def generate_positive_pay_csv(checks: list[IssuedCheck]) -> str:
    """Generate CSV positive pay file."""
    lines = ["check_number,amount,payee_name,issue_date,account_number,reference"]
    for chk in checks:
        lines.append(
            f"{chk.check_number},{chk.amount},{chk.payee_name},"
            f"{chk.issue_date.isoformat()},{chk.account_number},"
            f"{chk.reference or ''}"
        )
    return "\n".join(lines) + "\n"


def generate_positive_pay_fixed_width(checks: list[IssuedCheck]) -> str:
    """Generate fixed-width positive pay file (80 chars per record)."""
    lines: list[str] = []
    for chk in checks:
        amount_cents = int(chk.amount * 100)
        line = (
            chk.check_number[:11].ljust(11)
            + str(amount_cents).zfill(12)
            + chk.payee_name[:30].ljust(30)
            + chk.issue_date.strftime("%Y%m%d")
            + chk.account_number[:15].ljust(15)
            + (chk.reference or "")[:4].ljust(4)
        )
        lines.append(line[:80])
    return "\n".join(lines) + "\n"
