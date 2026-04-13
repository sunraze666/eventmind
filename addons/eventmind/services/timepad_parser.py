import re
import time
from datetime import datetime


TIMEPAD_URL = "https://afisha.timepad.ru/ekaterinburg"
SCROLL_PAUSE = 2
MAX_CLICKS = 50


def setup_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def close_cookie_popup(driver):
    from selenium.webdriver.common.by import By

    try:
        cookie_btn = driver.find_element(By.CSS_SELECTOR, ".ccookie-consent button, .cbtn--variant_primary")
        if cookie_btn and cookie_btn.is_displayed():
            cookie_btn.click()
            time.sleep(0.5)
    except Exception:
        pass


def click_show_more_button(driver):
    from selenium.webdriver.common.by import By

    try:
        buttons = driver.find_elements(
            By.XPATH,
            "//button[contains(text(), 'Показать') or contains(text(), 'Загрузить')]"
        )
        for btn in buttons:
            if btn.is_displayed() and btn.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                time.sleep(0.5)
                btn.click()
                return True
    except Exception:
        pass
    return False


def load_all_events(driver):
    from selenium.webdriver.common.by import By

    previous_count = 0
    no_change_count = 0
    click_count = 0

    while click_count < MAX_CLICKS:
        cards = driver.find_elements(By.CSS_SELECTOR, ".ceventcard, [class*='event-card'], [class*='EventCard']")
        current_count = len(cards)

        if current_count == previous_count:
            no_change_count += 1
            if no_change_count >= 2:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(SCROLL_PAUSE)
                if not click_show_more_button(driver):
                    break
                no_change_count = 0
        else:
            no_change_count = 0
            previous_count = current_count
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE)
            click_show_more_button(driver)

        click_count += 1
        time.sleep(1)

    return driver.find_elements(By.CSS_SELECTOR, ".ceventcard, [class*='event-card'], [class*='EventCard']")


def get_event_links_from_cards(cards):
    from selenium.webdriver.common.by import By

    links = set()
    for card in cards:
        try:
            link_elem = card.find_element(By.CSS_SELECTOR, "a[href*='/events/']")
            href = link_elem.get_attribute("href")
            if href:
                links.add(href.split("?")[0])
        except Exception:
            continue
    return list(links)


def parse_date_range(date_text):
    if not date_text:
        return None, None

    current_year = datetime.now().year
    months = {
        "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
        "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    }

    if "по" in date_text.lower() or "повторяется" in date_text.lower():
        return None, None

    time_range_match = re.search(r"(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})", date_text)
    date_start = None
    date_end = None

    for month_name, month_num in months.items():
        if month_name in date_text.lower():
            day_match = re.search(r"(\d{1,2})\s+" + month_name, date_text)
            if day_match:
                day = int(day_match.group(1))
                time_match = re.search(r"(\d{1,2}):(\d{2})", date_text)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))
                    date_start = datetime(current_year, month_num, day, hour, minute)
                    if time_range_match:
                        end_hour = int(time_range_match.group(3))
                        end_minute = int(time_range_match.group(4))
                        date_end = datetime(current_year, month_num, day, end_hour, end_minute)
                else:
                    date_start = datetime(current_year, month_num, day, 0, 0)
                break

    return date_start, date_end or date_start


def parse_event_details(driver, event_url):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    driver.get(event_url)
    time.sleep(2)
    close_cookie_popup(driver)

    event = {
        "url": event_url,
        "external_id": event_url.rstrip("/").split("/")[-1],
        "name": "",
        "description": "",
        "date_start": None,
        "date_end": None,
        "location": "",
        "price": "",
        "age_limit": "",
    }

    try:
        title = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
        event["name"] = title.text.strip()
    except Exception:
        event["name"] = "Без названия"

    desc_selectors = [
        "div[class*='Description-module__content']",
        "div[class*='description']",
        "div[data-testid='event-description']",
        "section[class*='description']",
        ".event-description",
        ".typography--article",
        "div[class*='AboutEvent']",
        "div[class*='event-about']",
    ]
    for selector in desc_selectors:
        try:
            desc_elem = driver.find_element(By.CSS_SELECTOR, selector)
            desc_text = desc_elem.text.strip()
            if desc_text and len(desc_text) > 50:
                event["description"] = desc_text
                break
        except Exception:
            continue

    date_selectors = [
        "[class*='EventInfo-module__date']",
        "[class*='date']",
        ".event-info__date",
        "time",
    ]
    for selector in date_selectors:
        try:
            date_elem = driver.find_element(By.CSS_SELECTOR, selector)
            date_text = date_elem.text.strip()
            if date_text and "cookie" not in date_text.lower():
                event["date_start"], event["date_end"] = parse_date_range(date_text)
                break
        except Exception:
            continue

    location_selectors = [
        "[class*='LocationInfo-module__location']",
        "[class*='location']",
        "[class*='address']",
        ".event-info__location",
        "[data-testid='event-location']",
    ]
    for selector in location_selectors:
        try:
            location_elem = driver.find_element(By.CSS_SELECTOR, selector)
            loc_text = location_elem.text.strip()
            if loc_text and "cookie" not in loc_text.lower():
                event["location"] = loc_text
                break
        except Exception:
            continue

    price_selectors = [
        "[class*='TicketInfo-module__price']",
        "[class*='price']",
        ".event-info__price",
    ]
    for selector in price_selectors:
        try:
            price_elem = driver.find_element(By.CSS_SELECTOR, selector)
            price_text = price_elem.text.strip()
            if price_text and ("₽" in price_text or "руб" in price_text):
                event["price"] = price_text
                break
        except Exception:
            continue

    age_selectors = [
        "[class*='age-limit']",
        "[class*='ageLimit']",
        "[class*='age']",
    ]
    for selector in age_selectors:
        try:
            age_elems = driver.find_elements(By.CSS_SELECTOR, selector)
            for age_elem in age_elems:
                age_text = age_elem.text.strip()
                if age_text and re.match(r"\d+\+", age_text):
                    event["age_limit"] = age_text
                    break
            if event["age_limit"]:
                break
        except Exception:
            continue

    return event


def fetch_timepad_events():
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    driver = setup_driver()
    try:
        driver.get(TIMEPAD_URL)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)
        close_cookie_popup(driver)

        cards = load_all_events(driver)
        links = get_event_links_from_cards(cards)

        events = []
        for link in links:
            events.append(parse_event_details(driver, link))
            time.sleep(0.5)

        return events
    finally:
        driver.quit()