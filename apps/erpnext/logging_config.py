import logging
import sys

def setup_logging(bootinfo=None):
    # Obtenir le logger racine de Frappe
    logger = logging.getLogger('frappe')

    # Ajouter un StreamHandler pour afficher les logs dans le terminal
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.ERROR)  # Limiter aux erreurs
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # Ajouter le handler au logger (éviter les doublons)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(console_handler)

    # Configurer le niveau de journalisation
    logger.setLevel(logging.ERROR)
    logger.propagate = True