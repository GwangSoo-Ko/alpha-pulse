from .html_report import generate_html_report
from .terminal import (
    print_history,
    print_investor_detail,
    print_macro_detail,
    print_pulse_report,
    print_sector_detail,
)

__all__ = [
    "print_pulse_report",
    "print_investor_detail",
    "print_sector_detail",
    "print_macro_detail",
    "print_history",
    "generate_html_report",
]
