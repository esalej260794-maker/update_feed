import requests
from lxml import etree
from geopy.geocoders import Nominatim
import time
import json
import os

# --- Файл кеша ---
CACHE_FILE = "geo_cache.json"

# --- Загрузка кеша ---
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        geo_cache = json.load(f)
else:
    geo_cache = {}

# --- Геокодер с кешем ---
geolocator = Nominatim(user_agent="real_estate_feed")

def geocode_address(address):
    if not address:
        return 0.0, 0.0
    if address in geo_cache:
        lat, lon = geo_cache[address]
        return float(lat), float(lon)
    try:
        location = geolocator.geocode(address + ", Россия")
        time.sleep(1)  # ограничение по Nominatim
        if location:
            lat, lon = location.latitude, location.longitude
            geo_cache[address] = (lat, lon)
            return lat, lon
    except Exception as e:
        print("Ошибка геокодирования:", address, e)
    geo_cache[address] = (0.0, 0.0)
    return 0.0, 0.0

# --- Ссылки на фиды ---
feeds = {
    "main": "https://progress.vtcrm.ru/xmlgen/WebsiteYMLFeed.xml",
    "in_park": "https://progress.vtcrm.ru/xmlgen/CianinparkFeed.xml",
    "novo_br": "https://idalite.ru/feed/26235f5e-76ef-4108-8e3e-82950637df0b",
    "aux_coords": "https://raw.githubusercontent.com/esalej260794-maker/tilda-map-data/refs/heads/main/WebsiteYML_next.xml"
}

# --- Загрузка XML ---
def load_feed(url):
    r = requests.get(url)
    return etree.fromstring(r.content)

main_feed = load_feed(feeds["main"])
in_park_feed = load_feed(feeds["in_park"])
novo_br_feed = load_feed(feeds["novo_br"])
aux_feed = load_feed(feeds["aux_coords"])

# --- Извлекаем currencies и categories ---
currencies_elem = main_feed.find("currencies")
categories_elem = main_feed.find("categories")

# --- Обработка основного фида ---
agents_bui = ["Евгения Серова","Виктория Набатова","Ольга Торопова","Наталья Квасова"]

# --- Функция для поиска координат в дополнительных фидах ---
def get_coords_from_aux(address, aux_feeds):
    for feed in aux_feeds:
        for obj in feed.findall(".//object"):
            addr = obj.findtext("Address") or ""
            if addr == address:
                lat = obj.findtext("Coordinates/Lat") or "0"
                lon = obj.findtext("Coordinates/Lng") or "0"
                if lat != "0" and lon != "0":
                    return float(lat), float(lon)
    return 0.0, 0.0

# --- Обновляем координаты в основном фиде ---
for offer in main_feed.findall(".//offer"):
    address_elem = offer.find(".//param[@name='Адрес']")
    if address_elem is not None:
        address_text = address_elem.text
        coords_elem = offer.find("coordinates")
        lat = coords_elem.get("lat") if coords_elem is not None else None
        lon = coords_elem.get("lon") if coords_elem is not None else None

        if not lat or lat == "0" or not lon or lon == "0":
            # 1. Пытаемся геокодер
            lat, lon = geocode_address(address_text)
            # 2. Если геокодер не дал результата, ищем в новостройках и в aux_feed
            if lat == 0.0 and lon == 0.0:
                lat, lon = get_coords_from_aux(address_text, [in_park_feed, novo_br_feed, aux_feed])
            if coords_elem is None:
                coords_elem = etree.SubElement(offer, "coordinates")
            coords_elem.set("lat", f"{lat:.6f}")
            coords_elem.set("lon", f"{lon:.6f}")

    # Офис
    agent = offer.find(".//param[@name='Имя агента']")
    office_val = "Буй" if agent is not None and agent.text in agents_bui else "Ярославль"
    office_elem = offer.find(".//param[@name='Офис']")
    if office_elem is None:
        office_elem = etree.SubElement(offer, "param", name="Офис")
    office_elem.text = office_val

# --- Функция преобразования объектов застройщика ---
def map_developer_flat(flat, jkschema_default):
    external_id = flat.findtext("ExternalId") or "0"
    offer = etree.Element("offer", id=external_id)
    
    etree.SubElement(offer, "categoryId").text = "101"
    
    rooms = flat.findtext("FlatRoomsCount") or "0"
    total_area = flat.findtext("TotalArea") or "0"
    jkschema_name = flat.findtext("JKSchema/Name") or jkschema_default
    offer_name = f"{rooms}-к, {total_area} кв.м, ЖК {jkschema_name}"
    etree.SubElement(offer, "name").text = offer_name
    
    price = flat.findtext("BargainTerms/Price") or "0"
    etree.SubElement(offer, "price").text = price
    
    desc = flat.findtext("Description") or ""
    etree.SubElement(offer, "description").text = desc
    
    material = flat.findtext("Building/MaterialType") or "unknown"
    etree.SubElement(offer, "param", name="Материал стен").text = material
    
    # Площади, комнаты, этаж, балкон, парковка
    etree.SubElement(offer, "param", name="Комнат").text = flat.findtext("FlatRoomsCount") or ""
    etree.SubElement(offer, "param", name="Площадь Дома").text = flat.findtext("TotalArea") or ""
    etree.SubElement(offer, "param", name="Жилая площадь").text = flat.findtext("LivingArea") or ""
    etree.SubElement(offer, "param", name="Площадь кухни").text = flat.findtext("KitchenArea") or ""
    etree.SubElement(offer, "param", name="Этаж").text = flat.findtext("FloorNumber") or ""
    etree.SubElement(offer, "param", name="Балкон").text = flat.findtext("BalconiesCount") or ""
    etree.SubElement(offer, "param", name="Парковка").text = flat.findtext("Building/Parking/Type") or ""
    
    addr = flat.findtext("Address") or ""
    etree.SubElement(offer, "param", name="Адрес").text = addr
    
    # Координаты
    lat = flat.findtext("Coordinates/Lat") or "0"
    lon = flat.findtext("Coordinates/Lng") or "0"
    coords = etree.SubElement(offer, "coordinates")
    try:
        coords.set("lat", f"{float(lat):.6f}")
        coords.set("lon", f"{float(lon):.6f}")
    except:
        coords.set("lat", "0.0")
        coords.set("lon", "0.0")
    
    # Фото
    layout_photo = flat.findtext("LayoutPhoto/FullUrl")
    if layout_photo:
        etree.SubElement(offer, "picture").text = layout_photo
    for photo in flat.findall("Photos/PhotoSchema"):
        url = photo.findtext("FullUrl")
        if url:
            etree.SubElement(offer, "picture").text = url
    
    # Офис
    etree.SubElement(offer, "param", name="Офис").text = "Ярославль"
    
    return offer

# --- Собираем все объекты ---
all_offers = []

# 1) Основной фид
for offer in main_feed.findall(".//offer"):
    all_offers.append(offer)

# 2) Новостройки (внизу)
for flat in in_park_feed.findall(".//object"):
    all_offers.append(map_developer_flat(flat, "Ин Парк"))

for flat in novo_br_feed.findall(".//object"):
    all_offers.append(map_developer_flat(flat, "ЖК Новое Брагино"))

# --- Финальный XML с shop, currencies и categories ---
shop = etree.Element("shop")

# Заполняем шапку shop
etree.SubElement(shop, "name").text = "Название магазина"
etree.SubElement(shop, "company").text = "Компания"
etree.SubElement(shop, "url").text = "https://example.com"

# currencies
if currencies_elem is not None:
    shop.append(currencies_elem)
else:
    curr = etree.SubElement(shop, "currencies")
    etree.SubElement(curr, "currency", id="RUR", rate="1")

# categories
if categories_elem is not None:
    shop.append(categories_elem)
else:
    cats = etree.SubElement(shop, "categories")
    # Можно здесь вставить все категории жестко, если нужно

# offers
offers_root = etree.SubElement(shop, "offers")
for offer in all_offers:
    offers_root.append(offer)

# --- Сохраняем финальный XML ---
tree = etree.ElementTree(shop)
tree.write("feed_final.xml", encoding="utf-8", xml_declaration=True, pretty_print=True)

# --- Сохраняем кеш ---
with open(CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(geo_cache, f, ensure_ascii=False, indent=2)

print("feed_final.xml создан успешно, кеш координат обновлён")
