"""Surveille la billetterie Opening Session Verbier et envoie un push ntfy si des billets sont dispo."""
import os
import re
import sys
import unicodedata

import requests

PAGES = {
    "Billet seul": "https://verbier4vallees.ch/en/online-shop/activities/opening-session_activity_410650",
    "Billet + train": "https://verbier4vallees.ch/fr/shop-en-ligne/activites/opening-session-saint-nicolas-express_activity_426820",
}

# Textes indiquant que ce n'est PAS dispo (comparés sans accents, en minuscules)
SOLD_OUT_MARKERS = [
    "not bookable", "sold out",
    "pas reservable", "plus reservable", "epuise", "complet",
    "nicht buchbar", "ausverkauft",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-CH,fr;q=0.9,en;q=0.8",
}

TOPIC = os.environ.get("NTFY_TOPIC", "")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def visible_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def notify(title: str, message: str, url: str, priority: str = "urgent") -> None:
    if not TOPIC:
        print("NTFY_TOPIC absent, pas de notification envoyee")
        return
    requests.post(
        f"https://ntfy.sh/{TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": title, "Priority": priority, "Click": url, "Tags": "ski,santa"},
        timeout=15,
    )


def main() -> int:
    if os.environ.get("TEST_NOTIFY") == "true":
        notify("Test Verbier", "Le watcher fonctionne.", PAGES["Billet seul"], "default")

    errors = 0
    for name, url in PAGES.items():
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"[{name}] ERREUR acces page : {e}")
            errors += 1
            continue

        text = norm(visible_text(r.text))
        if "opening session" not in text:
            print(f"[{name}] Page inattendue (pas de 'Opening Session'), verifier l'URL")
            errors += 1
            continue

        found = [m for m in SOLD_OUT_MARKERS if m in text]
        print(f"[{name}] 2026 mentionne : {'2026' in text} | marqueurs : {found or 'AUCUN'}")

        if not found:
            notify(f"Verbier : {name} DISPO ?", f"{name} semble en vente. Fonce !", url)
            print(f"[{name}] >>> NOTIFICATION ENVOYEE")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
