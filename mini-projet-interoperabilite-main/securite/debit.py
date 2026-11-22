"""Limitation de debit, par adresse appelante.

But : empecher qu'un appelant, par erreur de boucle ou par malveillance, vide la
base patient par patient ou tente des milliers de jetons. Le compteur d'echecs
d'authentification (jetons.CompteurEchecs) couvre la force brute sur le jeton ;
celui-ci couvre le volume total de requetes.

Algorithme : seau a jetons. Chaque appelant dispose de `par_minute` requetes par
minute, avec une reserve de `rafale` pour absorber un envoi groupe legitime
(le client de H2 envoie plusieurs dossiers de suite).

En memoire, donc valable pour un seul processus. Avec plusieurs workers uvicorn,
la limite effective est multipliee par le nombre de workers : en production il
faut un compteur partage ou un pare-feu applicatif en amont. C'est documente
dans docs/securite/politique-securite.md.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

# Routes consultees en permanence par les sondes de supervision : elles ne
# doivent pas consommer le quota d'echange.
CHEMINS_EXEMPTES = ("/health", "/metadata")


class SeauAJetons:
    """Un seau par cle (adresse IP), rempli en continu."""

    def __init__(self, par_minute: int, rafale: Optional[int] = None,
                 taille_max_table: int = 10_000):
        self.par_minute = max(1, par_minute)
        self.debit = self.par_minute / 60.0
        self.rafale = max(1, rafale if rafale is not None else max(10, self.par_minute // 4))
        self.taille_max_table = taille_max_table
        self._seaux = {}
        self._mutex = threading.Lock()

    def autoriser(self, cle: str, maintenant: Optional[float] = None) -> tuple:
        """Renvoie (autorise, secondes_a_attendre)."""
        horloge = time.monotonic() if maintenant is None else maintenant
        with self._mutex:
            if len(self._seaux) > self.taille_max_table:
                self._purger(horloge)
            niveau, dernier = self._seaux.get(cle, (float(self.rafale), horloge))
            niveau = min(float(self.rafale), niveau + (horloge - dernier) * self.debit)
            if niveau < 1.0:
                self._seaux[cle] = (niveau, horloge)
                return False, max(1, int((1.0 - niveau) / self.debit) + 1)
            self._seaux[cle] = (niveau - 1.0, horloge)
            return True, 0

    def _purger(self, horloge: float) -> None:
        """Oublie les seaux pleins : ils n'apportent plus d'information."""
        plein = float(self.rafale) - 0.001
        for cle in [c for c, (niveau, dernier) in self._seaux.items()
                    if min(float(self.rafale), niveau + (horloge - dernier) * self.debit) >= plein]:
            self._seaux.pop(cle, None)
