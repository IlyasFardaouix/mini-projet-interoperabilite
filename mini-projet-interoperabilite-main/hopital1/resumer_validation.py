"""Resume un rapport JSON du validateur officiel HL7, sans la narration XHTML."""

from collections import Counter
import json
from pathlib import Path
import sys


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage : python resumer_validation.py validation/rapport_aller.json")
    rapport = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if rapport.get("resourceType") != "OperationOutcome":
        raise SystemExit("Rapport OperationOutcome attendu.")
    issues = rapport.get("issue", [])
    comptes = Counter(i.get("severity", "unknown") for i in issues)
    print(" | ".join(f"{s}: {comptes[s]}" for s in ("fatal", "error", "warning", "information")))
    for issue in issues:
        if issue.get("severity") in ("fatal", "error"):
            print("; ".join(issue.get("expression", [])))
            print(issue.get("details", {}).get("text") or issue.get("diagnostics", ""))
    return 1 if comptes["fatal"] + comptes["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
