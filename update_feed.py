import requests
import xml.etree.ElementTree as ET
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time, json, os

# --- Настройки ---
FEEDS = [
    "https://progress.vtcrm.ru/xmlgen/CianinparkFeed.xml",
    "https://idalite.ru/feed/26235f5e-76ef-4108-8e3e-82950637df0b",
    "https://progress.vtcrm.ru/xmlgen/WebsiteYMLFeed.xml"
]
FINAL_FEED = "feed_final.xml"
CACHE_FILE = "geo_cache.json"

# --- Геокодер и кэш ---
geolocator = Nominatim(user_agent="feed_updater")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        geo_cache = json.load(f)
else:
    geo_cache = {}

def normalize_address(address: str) -> str:
    """Преобразует адрес к более читаемому виду для геокодера"""
    if not address:
        return ""
    replacements = {
        "г ": "город ",
        "ул ": "улица ",
        "обл": "область",
        "р-н": "район",
        "д ": "дом ",
    }
    for k, v in replacements.items():
        address = address.replace(k, v)
    if "Россия" not in address:
        address += ", Россия"
    return address.strip()

def get_coordinates(address):
    """Получает координаты, используя кэш и повторы"""
    if not address:
        return 0.0, 0.0
    if address in geo_cache:
        return geo_cache[address]

    normalized = normalize_address(address)
    for attempt in range(3):
        try:
            location = geocode(normalized)
            if location:
                lat, lon = location.latitude, location.longitude
                geo_cache[address] = (lat, lon)
                return lat, lon
        except Exception:
            time.sleep(1)
            continue
    print(f"⚠️ Не удалось геокодировать: {address}")
    geo_cache[address] = (0.0, 0.0)
    return 0.0, 0.0

# --- Сбор всех фидов ---
root_final = ET.Element("root")

for url in FEEDS:
    print(f"📥 Обработка фида: {url}")
    response = requests.get(url)
    response.encoding = "utf-8"

    tree = ET.fromstring(response.text)
    for offer in tree.findall(".//offer"):
        addr_elem = offer.find(".//param[@name='Адрес']")
        if addr_elem is not None:
            address = addr_elem.text
            lat, lon = get_coordinates(address)

            coords_elem = offer.find("coordinates")
            if coords_elem is None:
                coords_elem = ET.SubElement(offer, "coordinates")
            coords_elem.set("lat", str(lat))
            coords_elem.set("lon", str(lon))

        root_final.append(offer)

# --- Сохраняем кэш и финальный фид ---
with open(CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(geo_cache, f, ensure_ascii=False, indent=2)

tree_final = ET.ElementTree(root_final)
tree_final.write(FINAL_FEED, encoding="utf-8", xml_declaration=True)
print(f"✅ Финальный фид сохранён в {FINAL_FEED}")

