"""Cree une fois le jeton local dans .env, sans l'afficher ni le remplacer."""

from pathlib import Path
import secrets

from dotenv import dotenv_values, set_key


def main():
    fichier = Path(__file__).with_name(".env")
    if not fichier.exists():
        raise SystemExit("Creer le fichier .env avec la configuration Oracle avant cette etape.")
    if (dotenv_values(fichier).get("H1_API_TOKEN") or "").strip():
        print("H1_API_TOKEN existe deja : valeur conservee.")
    else:
        set_key(fichier, "H1_API_TOKEN", secrets.token_urlsafe(32), quote_mode="never")
        print("H1_API_TOKEN ajoute au fichier .env.")
    print("Redemarrer Uvicorn pour charger le jeton. Ne pas partager le fichier .env.")


if __name__ == "__main__":
    main()
