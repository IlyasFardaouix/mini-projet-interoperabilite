"""En-tetes de securite HTTP appliques a toutes les reponses des deux API.

Les deux API servent des donnees de sante. Les en-tetes ci-dessous ferment les
chemins de fuite les plus courants : mise en cache par un intermediaire,
inclusion dans une page tierce, devinette du type de contenu, envoi de l'URL
complete (qui contient un identifiant de patient) a un site externe.

`Cache-Control: no-store` est deja pose par H1 sur ses reponses de dossier
(hopital1/app.py). On le generalise ici a toutes les reponses, y compris les
erreurs, qui peuvent contenir des indices sur l'existence d'un patient.
"""

from __future__ import annotations

ENTETES_BASE = {
    # Aucune mise en cache, nulle part : ni navigateur, ni proxy, ni disque.
    "Cache-Control": "no-store, no-cache, must-revalidate, private",
    "Pragma": "no-cache",
    "Expires": "0",
    # Le navigateur ne devine pas le type : evite qu'un JSON soit interprete en HTML.
    "X-Content-Type-Options": "nosniff",
    # Ces API ne sont pas faites pour etre affichees dans un cadre.
    "X-Frame-Options": "DENY",
    # L'URL contient un identifiant de patient : elle ne doit jamais partir en Referer.
    "Referrer-Policy": "no-referrer",
    # Une API JSON n'a besoin d'aucune ressource externe, d'aucun script, d'aucun cadre.
    "Content-Security-Policy": (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    ),
    # Aucun capteur du poste client n'est utile a une API.
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(), usb=(), payment=()",
    # Pas de partage de ressources entre origines : aucun site web n'appelle ces API.
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}

# Pose uniquement quand la requete est arrivee en HTTPS : annoncer HSTS en clair
# n'a aucun effet utile et peut bloquer un poste de test.
HSTS = "max-age=31536000; includeSubDomains"

# En-tetes de reponse a supprimer : ils annoncent la pile technique et sa version.
ENTETES_A_RETIRER = ("server", "x-powered-by")

# La documentation interactive (/docs, /redoc) a besoin de charger ses scripts
# depuis un CDN : la politique « default-src 'none' » la casserait.
CHEMINS_SANS_CSP = ("/docs", "/redoc", "/openapi.json")


def entetes_pour(chemin: str, *, https: bool) -> dict:
    """En-tetes a appliquer a la reponse d'une requete sur `chemin`."""
    entetes = dict(ENTETES_BASE)
    if https:
        entetes["Strict-Transport-Security"] = HSTS
    if chemin.startswith(CHEMINS_SANS_CSP):
        entetes.pop("Content-Security-Policy", None)
        entetes.pop("Cross-Origin-Resource-Policy", None)
    return entetes
