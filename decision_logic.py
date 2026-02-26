
 #decision_logic.py
# JSON-driven rules for the three-number Decision Tool (EB, YM, RAC).
# The engine evaluates rules in order and returns the first matching result.

from typing import Dict, Any, List, Tuple, Optional

Number = float | int

def _get_num(value: Any) -> Optional[Number]:
    try:
        # allow None to propagate; callers will guard
        return float(value)
    except Exception:
        return None

def _match_one(val: Number, cond: Dict[str, Any]) -> bool:
    """
    Match a single number against a condition dict with keys like:
      lt, lte, gt, gte, eq, between
    'between' expects [min, max] and is inclusive.
    """
    if val is None:
        return False

    if "eq" in cond and val != float(cond["eq"]):
        return False
    if "lt" in cond and not (val < float(cond["lt"])):
        return False
    if "lte" in cond and not (val <= float(cond["lte"])):
        return False
    if "gt" in cond and not (val > float(cond["gt"])):
        return False
    if "gte" in cond and not (val >= float(cond["gte"])):
        return False
    if "between" in cond:
        lo, hi = cond["between"]
        if not (float(lo) <= val <= float(hi)):
            return False
    return True

def _matches_rule(eb: Number, ym: Number, rac: Number, when: Dict[str, Any]) -> bool:
    """
    'when' is a dict that may contain conditions for 'eb', 'ym', 'tc'.
    Each of those is itself a dict of comparison operators (see _match_one).
    If a key isn't present, it's treated as "no constraint" for that variable.
    """
    for key, val_cond in (("eb", eb), ("ym", ym), ("rac", rac)):
        cond = when.get(key)
        if cond is not None:
            if not _match_one(val_cond, cond):
                return False
    return True

def evaluate_triplet(nums: List[Any], rules_doc: Dict[str, Any] | None) -> Tuple[str, str]:
    """
    Evaluate the (EB, YM, RAC) triple against a rules document loaded from JSON.

    rules_doc structure:
    {
      "rule_version": "2025-12-10",
      "rules": [
        {"when": {"eb": {"lt": 1}, "ym": {"lte": 1}, "rac": {"lte": 20}}, "result": "Green"},
        ...
      ],
      "default": "Red"
    }
    """
    if not isinstance(nums, list) or len(nums) != 3:
        return ("Invalid", "Please provide exactly three numbers.")

    eb, ym, rac = (_get_num(nums[0]), _get_num(nums[1]), _get_num(nums[2]))
    if eb is None or ym is None or rac is None:
        return ("Invalid", "All three values must be numeric (integers/decimals).")

    # If we don't have a valid rules document, fail with a sensible default
    if not isinstance(rules_doc, dict) or "rules" not in rules_doc:
        return ("Invalid", "Decision rules are not available. Please contact the administrator.")

    # Evaluate in order; the first match wins
    for i, rule in enumerate(rules_doc.get("rules", [])):
        when = rule.get("when", {})
        if _matches_rule(eb, ym, rac, when):
            label = str(rule.get("result", "Fail"))
            explain = rule.get("explanation") or f"Matched rule #{i+1} ({label})."
            return (label, explain)

    # Fallback
    default_label = str(rules_doc.get("default", "Invalid"))
    return (default_label, f"No rule matched. Using default: {default_label}.")
