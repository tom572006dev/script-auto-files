#!/usr/bin/env python3
"""
Export iCloud "Hide My Email" addresses to CSV.

Usage:
    python export_hide_my_email.py

The browser will open. Log in manually (with your Apple ID + 2FA),
then the script will navigate to Hide My Email and extract all addresses.
"""

import csv
import time
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


ICLOUD_URL = "https://www.icloud.com"
HIDE_MY_EMAIL_URL = "https://www.icloud.com/settings/"

LOGIN_TIMEOUT = 120   # seconds to wait for manual login
NAV_TIMEOUT   = 30   # seconds for navigation waits
SCROLL_PAUSE  = 1.5  # seconds between scrolls to load more items


def build_driver(headless: bool = False) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def wait_for_login(driver: webdriver.Chrome) -> None:
    """Wait until the user confirms they have completed login."""
    print("\n[1/4] Browser opened on iCloud.")
    print("      --> Connecte-toi avec ton Apple ID + code 2FA dans le navigateur.")
    input("      --> Appuie sur ENTRÉE ici une fois que tu es bien connecté : ")
    print("[1/4] Login confirmé.")


def navigate_to_hide_my_email(driver: webdriver.Chrome) -> None:
    """Navigate to the iCloud Settings > Hide My Email section."""
    print("[2/4] Navigating to iCloud Settings...")
    driver.get(HIDE_MY_EMAIL_URL)
    wait = WebDriverWait(driver, NAV_TIMEOUT)

    # Try to find and click the "Hide My Email" entry in settings
    selectors_section = [
        (By.XPATH, "//*[contains(translate(text(),'HIDEMAIL','hidemail'), 'hide my email')]"),
        (By.XPATH, "//*[contains(@class,'hide') and contains(@class,'email')]"),
        (By.PARTIAL_LINK_TEXT, "Hide My Email"),
        (By.XPATH, "//a[contains(@href, 'hide')]"),
    ]

    clicked = False
    for by, value in selectors_section:
        try:
            el = wait.until(EC.element_to_be_clickable((by, value)))
            el.click()
            clicked = True
            print("[2/4] Clicked 'Hide My Email' section.")
            time.sleep(2)
            break
        except TimeoutException:
            continue

    if not clicked:
        print("[2/4] Could not auto-click 'Hide My Email'. Waiting 15s for you to open it manually...")
        time.sleep(15)


def scroll_to_load_all(driver: webdriver.Chrome) -> None:
    """Scroll the email list container to trigger lazy-loading of all entries."""
    print("[3/4] Scrolling to load all addresses...")
    # Try common scrollable containers used by iCloud
    container_selectors = [
        (By.CSS_SELECTOR, "[class*='list']"),
        (By.CSS_SELECTOR, "[class*='scroll']"),
        (By.CSS_SELECTOR, "main"),
        (By.TAG_NAME, "body"),
    ]

    container = None
    for by, sel in container_selectors:
        try:
            container = driver.find_element(by, sel)
            break
        except NoSuchElementException:
            continue

    last_count = 0
    for _ in range(50):  # max 50 scroll attempts
        if container:
            driver.execute_script("arguments[0].scrollTop += 800", container)
        else:
            driver.execute_script("window.scrollBy(0, 800)")
        time.sleep(SCROLL_PAUSE)
        current = len(extract_emails_from_page(driver))
        if current == last_count and current > 0:
            break
        last_count = current


def extract_emails_from_page(driver: webdriver.Chrome) -> list[dict]:
    """Extract all Hide My Email addresses visible in the DOM."""
    results = []
    seen = set()

    # Selectors that iCloud uses for alias list items (may change with UI updates)
    email_selectors = [
        # Generic: any element whose text looks like an @icloud.com alias
        (By.XPATH, "//*[contains(text(), '@privaterelay.appleid.com')]"),
        (By.XPATH, "//*[contains(text(), '@icloud.com') and string-length(text()) < 80]"),
        # Structured list rows
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
                    # Try to grab the label/note from a sibling element
                    label = ""
                    try:
                        parent = el.find_element(By.XPATH, "..")
                        spans = parent.find_elements(By.TAG_NAME, "span")
                        for s in spans:
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


def save_csv(emails: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["email", "label"])
        writer.writeheader()
        writer.writerows(emails)


def main():
    driver = build_driver(headless=False)
    try:
        driver.get(ICLOUD_URL)
        wait_for_login(driver)
        navigate_to_hide_my_email(driver)
        scroll_to_load_all(driver)

        print("[3/4] Extracting addresses...")
        emails = extract_emails_from_page(driver)

        if not emails:
            print("\n[!] No addresses found automatically.")
            print("    Tips:")
            print("    - Make sure you are on the 'Hide My Email' page in iCloud Settings.")
            print("    - The iCloud UI may have changed; try running with DEBUG=1 to dump the page source.")
            print("    - You can scroll manually, then press Enter to retry extraction.")
            input("    Press Enter to retry, or Ctrl+C to quit: ")
            emails = extract_emails_from_page(driver)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/home/user/script-auto-files/hide_my_email_{timestamp}.csv"
        save_csv(emails, output_path)

        print(f"\n[4/4] Done! {len(emails)} address(es) saved to:")
        print(f"      {output_path}")

        if len(emails) == 0:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nAborted by user.")
    finally:
        input("\nPress Enter to close the browser...")
        driver.quit()


if __name__ == "__main__":
    main()
