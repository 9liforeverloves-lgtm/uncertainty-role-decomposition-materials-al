from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

import numpy as np

try:
    from pymatgen.core import Composition
except Exception:  # pragma: no cover
    Composition = None


@dataclass(frozen=True)
class SplitResult:
    source: np.ndarray
    target: np.ndarray
    diagnostic: np.ndarray
    group_by_index: tuple[str, ...]
    protocol: str
    seed: int

    def validate(self, n: int, min_source: int, min_target: int, min_diagnostic: int) -> None:
        sets = [set(map(int, self.source)), set(map(int, self.target)), set(map(int, self.diagnostic))]
        if sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2]:
            raise ValueError("split partitions overlap")
        if set.union(*sets) != set(range(n)):
            raise ValueError("split partitions do not cover all records")
        if len(self.source) < min_source or len(self.target) < min_target or len(self.diagnostic) < min_diagnostic:
            raise ValueError("split does not satisfy minimum sample requirements")
        if self.protocol == "chemical_system_ood":
            groups = [set(self.group_by_index[i] for i in part) for part in (self.source, self.target, self.diagnostic)]
            if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
                raise ValueError("chemical-system group leakage")


def chemical_system(formula: str) -> str:
    if Composition is not None:
        try:
            elements = sorted(str(e) for e in Composition(str(formula)).elements)
            if elements:
                return "-".join(elements)
        except Exception:
            pass
    elements = sorted(set(re.findall(r"[A-Z][a-z]?", str(formula))))
    if not elements:
        raise ValueError(f"formula cannot be parsed: {formula!r}")
    return "-".join(elements)


def _stable_key(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}|{value}".encode()).hexdigest()


class IIDRecordSplit:
    name = "iid_record"

    def split(self, formulas, ids, seed: int, source_fraction=.20, diagnostic_fraction=.20,
              min_source=10, min_target=20, min_diagnostic=10) -> SplitResult:
        n = len(ids)
        order = np.random.default_rng(seed).permutation(n)
        ns = max(min_source, int(round(n * source_fraction)))
        nd = max(min_diagnostic, int(round(n * diagnostic_fraction)))
        if n - ns - nd < min_target:
            raise ValueError("insufficient records for IID minimums")
        groups = tuple(f"record:{x}" for x in ids)
        result = SplitResult(np.sort(order[:ns]), np.sort(order[ns:n-nd]), np.sort(order[n-nd:]), groups, self.name, seed)
        result.validate(n, min_source, min_target, min_diagnostic)
        return result


class ChemicalSystemOODSplit:
    name = "chemical_system_ood"

    def split(self, formulas, ids, seed: int, source_fraction=.20, diagnostic_fraction=.20,
              min_source=10, min_target=20, min_diagnostic=10) -> SplitResult:
        groups = tuple(chemical_system(x) for x in formulas)
        by_group: dict[str, list[int]] = {}
        for i, group in enumerate(groups):
            by_group.setdefault(group, []).append(i)
        if len(by_group) < 3:
            raise ValueError("fewer than three chemical-system groups")
        targets = {"source": len(ids) * source_fraction, "diagnostic": len(ids) * diagnostic_fraction,
                   "target": len(ids) * (1-source_fraction-diagnostic_fraction)}
        assigned = {k: [] for k in targets}
        counts = {k: 0 for k in targets}
        ordered = sorted(by_group, key=lambda g: (-len(by_group[g]), _stable_key(seed, g)))
        for group in ordered:
            role = max(targets, key=lambda k: (targets[k] - counts[k], -counts[k], k))
            assigned[role].extend(by_group[group]); counts[role] += len(by_group[group])
        result = SplitResult(np.array(sorted(assigned["source"])), np.array(sorted(assigned["target"])),
                             np.array(sorted(assigned["diagnostic"])), groups, self.name, seed)
        result.validate(len(ids), min_source, min_target, min_diagnostic)
        return result


def make_split(name: str):
    if name == "iid_record": return IIDRecordSplit()
    if name == "chemical_system_ood": return ChemicalSystemOODSplit()
    raise KeyError(name)
