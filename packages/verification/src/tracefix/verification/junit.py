from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestCase:
    nodeid: str
    outcome: str  # passed, failed, skipped, error
    message: str | None = None


@dataclass
class Inventory:
    cases: list[TestCase]
    collected: int
    errors: list[str]

    @property
    def ids(self) -> set[str]:
        return {c.nodeid for c in self.cases}

    @property
    def failed_ids(self) -> set[str]:
        return {c.nodeid for c in self.cases if c.outcome in {"failed", "error"}}

    @property
    def skipped_ids(self) -> set[str]:
        return {c.nodeid for c in self.cases if c.outcome == "skipped"}

    @property
    def passed_ids(self) -> set[str]:
        return {c.nodeid for c in self.cases if c.outcome == "passed"}

    def signature(self) -> str:
        failed = sorted(self.failed_ids)
        return "|".join(failed) if failed else "<none>"


def parse_junit(path: Path) -> Inventory:
    if not path.exists():
        return Inventory([], 0, ["missing junit xml"])
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        if raw.count("<") > 50_000:
            return Inventory([], 0, ["junit xml too large"])
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return Inventory([], 0, [f"malformed junit xml: {exc}"])
    cases: list[TestCase] = []
    suites = root.findall(".//testcase")
    if root.tag == "testcase":
        suites = [root]
    for node in suites:
        classname = node.attrib.get("classname", "")
        name = node.attrib.get("name", "")
        # Keep only the module tail so inventory is independent of workdir path.
        if "." in classname:
            parts = classname.split(".")
            for i, part in enumerate(parts):
                if part == "tests" or part.startswith("test_"):
                    classname = ".".join(parts[i:])
                    break
            else:
                classname = parts[-1]
        nodeid = f"{classname}::{name}" if classname else name
        if node.find("failure") is not None:
            msg = (node.find("failure").attrib.get("message") if node.find("failure") is not None else None)
            cases.append(TestCase(nodeid, "failed", msg))
        elif node.find("error") is not None:
            cases.append(TestCase(nodeid, "error", None))
        elif node.find("skipped") is not None:
            cases.append(TestCase(nodeid, "skipped", None))
        else:
            cases.append(TestCase(nodeid, "passed", None))
    if not cases:
        return Inventory([], 0, ["empty collection"])
    return Inventory(cases, len(cases), [])


def compare_inventories(baseline: Inventory, candidate: Inventory) -> list[str]:
    errors: list[str] = []
    disappeared = baseline.ids - candidate.ids
    if disappeared:
        errors.append(f"tests disappeared: {sorted(disappeared)}")
    new_skips = candidate.skipped_ids - baseline.skipped_ids
    if new_skips:
        errors.append(f"new skips: {sorted(new_skips)}")
    new_failures = candidate.failed_ids - baseline.failed_ids
    if new_failures:
        errors.append(f"new failures: {sorted(new_failures)}")
    if candidate.errors:
        errors.extend(candidate.errors)
    return errors
