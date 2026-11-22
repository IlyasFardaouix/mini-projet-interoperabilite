"""Interface web du personnel, commune aux deux hopitaux.

Chaque API (H1 et H2) sert la meme page sous /ui et quelques routes d'appui sous
/api/ui/. Le code de la page est identique ; seul l'adaptateur change (Oracle d'un
cote, MongoDB de l'autre). Voir docs/interface.md.

    from interface import installer_interface
    installer_interface(app, service="H1", adaptateur=AdaptateurH1())
"""

from .routes import ErreurInterface, installer_interface

__all__ = ["ErreurInterface", "installer_interface"]
