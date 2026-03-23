#!/usr/bin/env python3
"""
Export iCloud "Hide My Email" addresses to CSV.

Setup (une seule fois) :
    safaridriver --enable
    Puis dans Safari : menu Développement > Autoriser l'automatisation à distance

Usage :
    python3 export_hide_my_email.py

Safari s'ouvre avec ta session iCloud existante — pas besoin de te reconnecter.
"""

import csv
import time
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.safari.options import Options as SafariOptions


ICLOUD_URL        = "https://www.icloud.com"
HIDE_MY_EMAIL_URL = "https://www.icloud.com/settings/"

NAV_TIMEOUT  = 30   # secondes d'attente pour la navigation
SCROLL_PAUSE = 1.5  # secondes entre chaque scroll


def build_driver() -> webdriver.Safari:
    options = SafariOptions()
    driver = webdriver.Safari(options=options)
    driver.set_window_size(1400, 900)
    return driver


def check_logged_in(driver: webdriver.Safari) -> None:
    print("\n[1/4] Vérification de la session iCloud...")
    time.sleep(4)
    url = driver.current_url.lower()
    if "signin" in url or "appleid" in url or "idmsa" in url:
        print("      Session expirée. Connecte-toi dans Safari.")
        input("      Appuie sur ENTRÉE une fois connecté : ")
    else:
        print("[1/4] Session active.")


def navigate_to_hide_my_email(driver: webdriver.Safari) -> None:
    print("[2/4] Ouverture de iCloud Settings...")
    driver.get(HIDE_MY_EMAIL_URL)
    print()
    print("  Dans Safari :")
    print("  1. Attends que la page se charge complètement")
    print("  2. Clique sur 'Hide My Email' (ou 'Masquer mon adresse e-mail')")
    print("  3. Attends que la liste de tes adresses apparaisse")
    print()
    input("  Appuie sur ENTRÉE quand la liste est visible : ")


def scroll_to_load_all(driver: webdriver.Safari) -> None:
    print("[3/4] Défilement pour charger toutes les adresses...")
    last_count = 0
    for _ in range(60):
        driver.execute_script("window.scrollBy(0, 600)")
        time.sleep(SCROLL_PAUSE)
        current = len(extract_emails_from_page(driver))
        if current == last_count and current > 0:
            break
        last_count = current
    print(f"      {last_count} adresse(s) trouvée(s) après défilement.")


def extract_emails_from_page(driver: webdriver.Safari) -> list:
    results = []
    seen = set()

    email_selectors = [
        (By.XPATH, "//*[contains(text(), '@privaterelay.appleid.com')]"),
        (By.XPATH, "//*[contains(text(), '@icloud.com') and string-length(text()) < 80]"),
        (By.CSS_SELECTOR, "[class*='EmailRow'] [class*='email']"),
        (By.CSS_SELECTOR, "[class*='hideMyEmail'] [class*='address']"),
        (By.CSS_SELECTOR, "li[class*='item'] span[class*='email']"),
    ]

    for by, sel in email_selectors:
        try:
            elements = driver.find_elements(by, sel)
            for el in elements:
                text = el.text.strip()
                if "@" in text and text not in seen:
                    seen.add(text)
                    label = ""
                    try:
                        parent = el.find_element(By.XPATH, "..")
                        for s in parent.find_elements(By.TAG_NAME, "span"):
                            t = s.text.strip()
                            if t and t != text:
                                label = t
                                break
                    except Exception:
                        pass
                    results.append({"email": text, "label": label})
        except Exception:
            continue

    return results


def save_csv(emails: list, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["email", "label"])
        writer.writeheader()
        writer.writerows(emails)


def main():
    print("=" * 55)
    print("  Export iCloud Hide My Email → CSV")
    print("=" * 55)
    print()
    print("Prérequis (une seule fois si pas encore fait) :")
    print("  1. Dans le Terminal :  safaridriver --enable")
    print("  2. Dans Safari       :  Développement > Autoriser l'automatisation à distance")
    print()
    input("Appuie sur ENTRÉE pour ouvrir Safari : ")

    driver = build_driver()
    try:
        driver.get(ICLOUD_URL)
        check_logged_in(driver)
        navigate_to_hide_my_email(driver)
        scroll_to_load_all(driver)

        print("[3/4] Extraction des adresses...")
        emails = extract_emails_from_page(driver)

        if not emails:
            print()
            print("[!] Aucune adresse trouvée automatiquement.")
            print("    Navigue manuellement dans Safari jusqu'à la liste")
            print("    de tes adresses Hide My Email, puis appuie sur ENTRÉE.")
            input("    ENTRÉE pour réessayer : ")
            emails = extract_emails_from_page(driver)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{__import__('os').path.expanduser('~/Desktop')}/hide_my_email_{timestamp}.csv"
        save_csv(emails, output_path)

        print()
        print(f"[4/4] {len(emails)} adresse(s) exportée(s) :")
        print(f"      {output_path}")

        if len(emails) == 0:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nInterrompu.")
    finally:
        input("\nAppuie sur ENTRÉE pour fermer Safari : ")
        driver.quit()


if __name__ == "__main__":
    main()
