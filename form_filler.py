"""
Script de remplissage automatique de formulaire d'inscription
Utilise Selenium WebDriver avec Python
"""

import time
import json
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.json") -> dict:
    """Charge la configuration depuis un fichier JSON."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier de config introuvable : {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_driver(headless: bool = False) -> webdriver.Chrome:
    """Crée et configure le driver Chrome."""
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # Désactive la détection de l'automatisation par certains sites
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)
    return driver


def fill_field(driver, wait, selector: dict, value: str, field_name: str = ""):
    """
    Remplit un champ de formulaire selon le sélecteur fourni.

    selector: {"by": "id"|"name"|"css"|"xpath", "value": "..."}
    """
    by_map = {
        "id":    By.ID,
        "name":  By.NAME,
        "css":   By.CSS_SELECTOR,
        "xpath": By.XPATH,
    }
    by = by_map.get(selector["by"], By.CSS_SELECTOR)

    try:
        element = wait.until(EC.presence_of_element_located((by, selector["value"])))
        element.clear()
        element.send_keys(value)
        logger.info("Champ '%s' rempli avec succès.", field_name or selector["value"])
    except TimeoutException:
        logger.error("Champ introuvable : %s", selector["value"])
        raise


def select_option(driver, wait, selector: dict, value: str, field_name: str = ""):
    """Sélectionne une option dans un <select>."""
    by_map = {
        "id":    By.ID,
        "name":  By.NAME,
        "css":   By.CSS_SELECTOR,
        "xpath": By.XPATH,
    }
    by = by_map.get(selector["by"], By.CSS_SELECTOR)

    try:
        element = wait.until(EC.presence_of_element_located((by, selector["value"])))
        select = Select(element)
        # Essaie par valeur visible, puis par valeur d'attribut
        try:
            select.select_by_visible_text(value)
        except Exception:
            select.select_by_value(value)
        logger.info("Option '%s' sélectionnée pour '%s'.", value, field_name)
    except TimeoutException:
        logger.error("Liste déroulante introuvable : %s", selector["value"])
        raise


def click_element(driver, wait, selector: dict, label: str = ""):
    """Clique sur un élément (bouton, checkbox, etc.)."""
    by_map = {
        "id":    By.ID,
        "name":  By.NAME,
        "css":   By.CSS_SELECTOR,
        "xpath": By.XPATH,
    }
    by = by_map.get(selector["by"], By.CSS_SELECTOR)

    try:
        element = wait.until(EC.element_to_be_clickable((by, selector["value"])))
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        element.click()
        logger.info("Clic sur '%s'.", label or selector["value"])
    except TimeoutException:
        logger.error("Élément non cliquable : %s", selector["value"])
        raise


def fill_registration_form(config: dict):
    """Remplit le formulaire d'inscription selon la configuration."""
    url        = config["url"]
    form_data  = config["form_data"]
    fields     = config["fields"]
    settings   = config.get("settings", {})
    headless   = settings.get("headless", False)
    wait_time  = settings.get("wait_timeout", 10)
    delay      = settings.get("delay_between_fields", 0.3)

    driver = create_driver(headless=headless)
    wait   = WebDriverWait(driver, wait_time)

    try:
        logger.info("Ouverture du site : %s", url)
        driver.get(url)
        time.sleep(1)  # Attente initiale pour le chargement

        # --- Remplissage des champs texte ---
        for field_key, field_config in fields.get("inputs", {}).items():
            value = form_data.get(field_key)
            if value is None:
                logger.warning("Valeur manquante pour le champ '%s', ignoré.", field_key)
                continue
            fill_field(driver, wait, field_config["selector"], str(value), field_key)
            time.sleep(delay)

        # --- Sélections dans les listes déroulantes ---
        for field_key, field_config in fields.get("selects", {}).items():
            value = form_data.get(field_key)
            if value is None:
                logger.warning("Valeur manquante pour la liste '%s', ignorée.", field_key)
                continue
            select_option(driver, wait, field_config["selector"], str(value), field_key)
            time.sleep(delay)

        # --- Cochage des cases à cocher ---
        for field_key, field_config in fields.get("checkboxes", {}).items():
            should_check = form_data.get(field_key, False)
            if should_check:
                by_map = {"id": By.ID, "name": By.NAME, "css": By.CSS_SELECTOR, "xpath": By.XPATH}
                by = by_map.get(field_config["selector"]["by"], By.CSS_SELECTOR)
                checkbox = wait.until(EC.presence_of_element_located((by, field_config["selector"]["value"])))
                if not checkbox.is_selected():
                    checkbox.click()
                logger.info("Case cochée : '%s'.", field_key)
            time.sleep(delay)

        # --- Soumission du formulaire ---
        if settings.get("submit", True):
            submit_cfg = fields.get("submit_button")
            if submit_cfg:
                click_element(driver, wait, submit_cfg["selector"], "Bouton de soumission")
            else:
                # Fallback : touche Entrée sur le dernier champ
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.RETURN)

            time.sleep(2)
            logger.info("Formulaire soumis. URL actuelle : %s", driver.current_url)
        else:
            logger.info("Soumission désactivée (settings.submit = false). Vérifiez le formulaire.")
            input("Appuyez sur Entrée pour fermer le navigateur...")

    except Exception as e:
        logger.error("Erreur lors du remplissage : %s", e)
        raise
    finally:
        if not settings.get("keep_open", False):
            driver.quit()
            logger.info("Navigateur fermé.")


def main():
    config = load_config("config.json")
    fill_registration_form(config)


if __name__ == "__main__":
    main()
