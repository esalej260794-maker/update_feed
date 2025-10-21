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
    address_key = " ".join(address.strip().lower().split())
    if address_key in geo_cache:
        lat, lon = geo_cache[address_key]
        return float(lat), float(lon)
    try:
        location = geolocator.geocode(address + ", Россия")
        time.sleep(1)
        if location:
            lat, lon = location.latitude, location.longitude
            geo_cache[address_key] = (lat, lon)
            return lat, lon
    except Exception as e:
        print("Ошибка геокодирования:", address, e)
    geo_cache[address_key] = (0.0, 0.0)
    return 0.0, 0.0

# --- Фиды ---
feeds = {
    "main": "https://progress.vtcrm.ru/xmlgen/WebsiteYMLFeed.xml",
    "in_park": "https://progress.vtcrm.ru/xmlgen/CianinparkFeed.xml",
    "novo_br": "https://idalite.ru/feed/26235f5e-76ef-4108-8e3e-82950637df0b",
    "aux_coords": "https://raw.githubusercontent.com/esalej260794-maker/tilda-map-data/refs/heads/main/WebsiteYML_next.xml"
}

def load_feed(url):
    r = requests.get(url)
    return etree.fromstring(r.content)

main_feed = load_feed(feeds["main"])
in_park_feed = load_feed(feeds["in_park"])
novo_br_feed = load_feed(feeds["novo_br"])
aux_feed = load_feed(feeds["aux_coords"])

agents_bui = ["Евгения Серова","Виктория Набатова","Ольга Торопова","Наталья Квасова"]

# --- Нормализация адреса для поиска ---
def normalize_address(addr):
    if not addr:
        return ""
    return " ".join(addr.strip().lower().split())

# --- Поиск координат в aux_feed ---
def get_coords_from_aux(address, aux_feeds):
    addr_norm = normalize_address(address)
    for feed in aux_feeds:
        for obj in feed.findall(".//object"):
            obj_addr = normalize_address(obj.findtext("Address") or "")
            if addr_norm == obj_addr:
                lat = obj.findtext("Coordinates/Lat") or "0"
                lon = obj.findtext("Coordinates/Lng") or "0"
                try:
                    lat_f = float(lat)
                    lon_f = float(lon)
                    if lat_f != 0.0 and lon_f != 0.0:
                        return lat_f, lon_f
                except:
                    continue
    return 0.0, 0.0

# --- Обновляем координаты в основном фиде ---
for offer in main_feed.findall(".//offer"):
    address_elem = offer.find(".//param[@name='Адрес']")
    if address_elem is not None:
        address_text = address_elem.text
        coords_elem = offer.find("coordinates")

        lat = lon = 0.0
        if coords_elem is not None:
            try:
                lat = float(coords_elem.get("lat", "0"))
                lon = float(coords_elem.get("lon", "0"))
            except:
                lat = lon = 0.0

        if lat == 0.0 and lon == 0.0:
            # 1. Геокодер
            lat, lon = geocode_address(address_text)
            # 2. Если геокодер не дал результата, ищем в aux_feed
            if lat == 0.0 and lon == 0.0:
                lat, lon = get_coords_from_aux(address_text, [aux_feed])

            # Создаем coordinates, если нет
            if coords_elem is None:
                coords_elem = etree.SubElement(offer, "coordinates")
            coords_elem.set("lat", f"{lat:.6f}")
            coords_elem.set("lon", f"{lon:.6f}")

    # --- Подстановка офиса ---
    agent = offer.find(".//param[@name='Имя агента']")
    office_val = "Буй" if agent is not None and agent.text in agents_bui else "Ярославль"
    office_elem = offer.find(".//param[@name='Офис']")
    if office_elem is None:
        office_elem = etree.SubElement(offer, "param", name="Офис")
    office_elem.text = office_val

# --- Маппинг новостроек ---
def map_developer_flat(flat, jkschema_default):
    external_id = flat.findtext("ExternalId") or "0"
    offer = etree.Element("offer", id=external_id)
    etree.SubElement(offer, "categoryId").text = "101"

    rooms = flat.findtext("FlatRoomsCount") or "0"
    total_area = flat.findtext("TotalArea") or "0"
    jkschema_name = flat.findtext("JKSchema/Name") or jkschema_default
    etree.SubElement(offer, "name").text = f"{rooms}-к, {total_area} кв.м, ЖК {jkschema_name}"
    etree.SubElement(offer, "price").text = flat.findtext("BargainTerms/Price") or "0"
    etree.SubElement(offer, "description").text = flat.findtext("Description") or ""
    etree.SubElement(offer, "param", name="Материал стен").text = flat.findtext("Building/MaterialType") or "unknown"

    # Площади, этаж, балкон, парковка
    etree.SubElement(offer, "param", name="Комнат").text = flat.findtext("FlatRoomsCount") or ""
    etree.SubElement(offer, "param", name="Площадь Дома").text = flat.findtext("TotalArea") or ""
    etree.SubElement(offer, "param", name="Жилая площадь").text = flat.findtext("LivingArea") or ""
    etree.SubElement(offer, "param", name="Площадь кухни").text = flat.findtext("KitchenArea") or ""
    etree.SubElement(offer, "param", name="Этаж").text = flat.findtext("FloorNumber") or ""
    etree.SubElement(offer, "param", name="Балкон").text = flat.findtext("BalconiesCount") or ""
    etree.SubElement(offer, "param", name="Парковка").text = flat.findtext("Building/Parking/Type") or ""
    etree.SubElement(offer, "param", name="Адрес").text = flat.findtext("Address") or ""

    # Координаты
    lat = float(flat.findtext("Coordinates/Lat") or "0")
    lon = float(flat.findtext("Coordinates/Lng") or "0")
    coords = etree.SubElement(offer, "coordinates")
    coords.set("lat", f"{lat:.6f}")
    coords.set("lon", f"{lon:.6f}")

    # Фото
    layout_photo = flat.findtext("LayoutPhoto/FullUrl")
    if layout_photo:
        etree.SubElement(offer, "picture").text = layout_photo
    for photo in flat.findall("Photos/PhotoSchema"):
        url = photo.findtext("FullUrl")
        if url:
            etree.SubElement(offer, "picture").text = url

    etree.SubElement(offer, "param", name="Офис").text = "Ярославль"
    return offer

# --- Собираем все объекты ---
all_offers = []
all_offers.extend(main_feed.findall(".//offer"))
all_offers.extend([map_developer_flat(f, "Ин Парк") for f in in_park_feed.findall(".//object")])
all_offers.extend([map_developer_flat(f, "ЖК Новое Брагино") for f in novo_br_feed.findall(".//object")])

# --- Финальный XML ---
shop = etree.Element("shop")
etree.SubElement(shop, "name")
etree.SubElement(shop, "company")
etree.SubElement(shop, "url")

# currencies
curr = etree.SubElement(shop, "currencies")
etree.SubElement(curr, "currency", id="RUR", rate="1")

# categories жестко вставляем
cats = etree.SubElement(shop, "categories")
category_data = [
    ("10", None, "Квартиры, комнаты"),
    ("100", "10", "Квартиры"),
    ("101", "10", "Новостройки"),
    ("102", "10", "Комнаты"),
    ("103", "10", "Доли"),
    ("20", None, "Коммерческая недвижимость"),
    ("200", "20", "Офис"),
    ("201", "20", "Здание"),
    ("202", "20", "Торговое помещение"),
    ("203", "20", "Помещение свободного назначения"),
    ("204", "20", "Производство"),
    ("205", "20", "Склад"),
    ("206", "20", "Коммерческая земля"),
    ("207", "20", "Готовый бизнес"),
    ("208", "20", "Гостиница"),
    ("209", "20", "Общепит"),
    ("30", None, "Дома, участки"),
    ("300", "30", "Дом"),
    ("301", "30", "Дача"),
    ("302", "30", "Таунхаус"),
    ("303", "30", "Коттедж"),
    ("304", "30", "Участок"),
    ("305", "30", "Часть дома"),
    ("40", None, "Гаражи, машиноместа"),
    ("400", "40", "Бокс"),
    ("401", "40", "Гараж"),
    ("402", "40", "Машиноместо")
]
for cid, parent, name in category_data:
    if parent:
        etree.SubElement(cats, "category", id=cid, parentId=parent).text = name
    else:
        etree.SubElement(cats, "category", id=cid).text = name

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
