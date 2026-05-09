"""Reporting helpers for factor framework results."""

from .performance_report import export_result_pickle


def generate_interactive_report(*args, **kwargs):
    from .interactive_report import generate_interactive_report as _generate

    return _generate(*args, **kwargs)

__all__ = ["export_result_pickle", "generate_interactive_report"]
