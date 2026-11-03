"""Surveille la billetterie Opening Session Verbier : alerte si dispo ou si le bandeau 'sold out' change."""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import requests

PAGES = {
    "Billet seul": "https://verbier4vallees.ch/fr/shop-en-ligne/activites/opening-session_activity_410650",
    "Billet + train": "https://verbier4vallees.ch/en/online-shop/activities/opening-session-st.nicholas-express_activity_426820",
}

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
STATE_FILE = Path("state.json")


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


def page_state(url: str) -> str:
    """Retourne '404', 'DISPO' ou la phrase du bandeau d'epuisement."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 404:
        return "404"
    r.raise_for_status()
    text = norm(visible_text(r.text))
    for m in SOLD_OUT_MARKERS:
        hit = re.search(r"[^.!]{0,120}" + re.escape(m) + r"[^.!]{0,40}", text)
        if hit:
            return "SOLDOUT: " + hit.group(0).strip()
    return "DISPO"


def main() -> int:
    if os.environ.get("TEST_NOTIFY") == "true":
        notify("Test Verbier", "Le watcher fonctionne.", PAGES["Billet seul"], "default")

    old = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    new, errors = {}, 0

    for name, url in PAGES.items():
        try:
            state = page_state(url)
        except requests.RequestException as e:
            print(f"[{name}] ERREUR : {e}")
            errors += 1
            new[name] = old.get(name, "")
            continue

        new[name] = state
        prev = old.get(name)
        print(f"[{name}] {state}  (avant : {prev})")

        if state == "DISPO":
            notify(f"Verbier : {name} DISPO !", f"{name} : plus de bandeau sold out. Fonce !", url)
            print(f"[{name}] >>> ALERTE DISPO")
        elif prev is not None and state != prev:
            notify(f"Verbier : {name} a change", f"Nouveau : {state[:150]}", url, "high")
            print(f"[{name}] >>> ALERTE CHANGEMENT")

    STATE_FILE.write_text(json.dumps(new, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
