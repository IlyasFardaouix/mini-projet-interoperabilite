"""Active le garde-fou de commit de ce dépôt Git."""

from pathlib import Path
import subprocess


RACINE = Path(__file__).resolve().parents[2]


def main() -> int:
    if not (RACINE / ".git").exists():
        print("Initialiser ou cloner le dépôt Git avant d'installer le hook.")
        return 1
    subprocess.run(["git", "-C", str(RACINE), "config", "--local",
                    "core.hooksPath", "securite/hooks"], check=True)
    print("Garde-fou de commit activé pour ce dépôt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
