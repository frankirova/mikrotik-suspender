"""Unit tests for the RouterOS adapter's pure helpers (no device involved)."""

from __future__ import annotations

from adapters.mikrotik_adapter import referenced_lists


def test_collects_src_and_dst_list_matchers():
    rules = [
        {"src-address-list": "suspendido"},
        {"dst-address-list": "morosos"},
        {"chain": "forward", "action": "drop"},
    ]

    assert referenced_lists(rules) == {"suspendido", "morosos"}


def test_strips_the_negation_prefix():
    rules = [{"src-address-list": "!suspendido"}]

    assert referenced_lists(rules) == {"suspendido"}


def test_ignores_rules_without_list_matchers():
    rules = [{"src-address": "10.0.0.0/8"}, {"comment": "sin listas"}]

    assert referenced_lists(rules) == set()


def test_deduplicates_repeated_names():
    rules = [
        {"src-address-list": "suspendido"},
        {"dst-address-list": "suspendido"},
    ]

    assert referenced_lists(rules) == {"suspendido"}
