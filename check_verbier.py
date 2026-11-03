"""Surveille la dispo Opening Session Verbier via l'API du shop et envoie un push ntfy."""
import os
import sys

import requests

ACTIVITIES = {
    "Billet seul": 410650,
    "Billet + train": 426820,
}
API = "https://verbier4vallees.ch/en/shop/product/available-dates-times?activity_id={}"
SHOP = "https://verbier4vallees.ch/en/online-shop"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}

TOPIC = os.environ.get("NTFY_TOPIC", "")


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


def find_slots(obj):
    """Trouve tous les creneaux (dicts avec une cle 'available'), ou qu'ils soient dans le JSON."""
    if isinstance(obj, dict):
        if "available" in obj:
            yield obj
        for v in obj.values():
            yield from find_slots(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from find_slots(v)


def main() -> int:
    if os.environ.get("TEST_NOTIFY") == "true":
        notify("Test Verbier", "Le watcher fonctionne.", SHOP, "default")

    errors = 0
    for name, act_id in ACTIVITIES.items():
        try:
            r = requests.get(API.format(act_id), headers=HEADERS, timeout=30)
            r.raise_for_status()
            slots = list(find_slots(r.json()))
        except (requests.RequestException, ValueError) as e:
            print(f"[{name}] ERREUR : {e}")
            errors += 1
            continue

        if not slots:
            print(f"[{name}] Aucun creneau dans la reponse : {r.text[:200]}")
            errors += 1
            continue

        for s in slots:
            avail = int(s.get("available") or 0)
            print(f"[{name}] {s.get('date')} : {avail}/{s.get('max')} dispo")
            if avail > 0:
                notify(
                    f"Verbier : {name} DISPO ({avail})",
                    f"{avail} places dispo pour le {s.get('date')}. Fonce !",
                    SHOP,
                )
                print(f"[{name}] >>> ALERTE ENVOYEE")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
