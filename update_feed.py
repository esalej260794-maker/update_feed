import requests
from lxml import etree
from geopy.geocoders import Nominatim
import time
import json
import os

CACHE_FILE = "geo_cache.json"

# --- CACHE ---
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        geo_cache = json.load(f)
else:
    geo_cache = {}

geolocator = Nominatim(user_agent="real_estate_feed_v3")

# Ярославская область (bbox чтобы не улетало в другие города)
REGION_VIEWBOX = (37.2, 56.0, 41.6, 58.9)


def normalize_address(addr):
    if not addr:
        return ""
    return " ".join(addr.strip().lower().split())


# --- защита от "центров региона" (Углич/Ярославль fallback) ---
def is_bad_fallback(lat, lon):
    # Ярославль центр
    if abs(lat - 57.6261) < 0.03 and abs(lon - 39.8845) < 0.03:
        return True

    # Углич центр (главная твоя проблема)
    if abs(lat - 57.5275) < 0.03 and abs(lon - 38.3314) < 0.03:
        return True

    return False


def geocode_address(address):
    if not address:
        return 0.0, 0.0

    key = normalize_address(address)

    # --- CACHE ---
    if key in geo_cache:
        lat, lon = geo_cache[key]
        if lat != 0.0 or lon != 0.0:
            return lat, lon

    parts = [p.strip() for p in address.split(",") if p.strip()]

    variants = []

    # 1. полный адрес
    variants.append(address)

    # 2. улица + город (если есть)
    if len(parts) >= 2:
        variants.append(", ".join(parts[:2]))

    # 3. только населённый пункт
    if len(parts) >= 1:
        variants.append(parts[0])

    for variant in variants:
        try:
            query = f"{variant}, Ярославская область, Россия"

            loc = geolocator.geocode(
                query,
                exactly_one=True,
                bounded=True,
                viewbox=REGION_VIEWBOX
            )

            time.sleep(1)

            if not loc:
                continue

            lat = float(loc.latitude)
            lon = float(loc.longitude)

            # ❌ отсекаем мусорные центры
            if is_bad_fallback(lat, lon):
                continue

            geo_cache[key] = (lat, lon)
            return lat, lon

        except Exception as e:
            print("Geocode error:", e)

    return 0.0, 0.0


# --- fallback: центр населённого пункта ---
def geocode_city_fallback(address):
    if not address:
        return 0.0, 0.0

    try:
        city = address.split(",")[0].strip()

        loc = geolocator.geocode(
            f"{city}, Ярославская область, Россия",
            exactly_one=True,
            bounded=True,
            viewbox=REGION_VIEWBOX
        )

        time.sleep(1)

        if loc:
            lat = float(loc.latitude)
            lon = float(loc.longitude)

            if not is_bad_fallback(lat, lon):
                return lat, lon

    except Exception as e:
        print("Fallback error:", e)

    return 0.0, 0.0


def resolve_coordinates(address):
    lat, lon = geocode_address(address)
    if lat != 0.0 or lon != 0.0:
        return lat, lon

    return geocode_city_fallback(address)


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


agents_bui = [
    "Евгения Серова",
    "Виктория Набатова",
    "Ольга Торопова",
    "Наталья Квасова"
]


# --- AUX coords ---
def get_coords_from_aux(address, aux_feed):
    addr_norm = normalize_address(address)

    for offer in aux_feed.findall(".//offer"):
        obj_addr = normalize_address(
            offer.findtext("param[@name='Адрес']") or ""
        )

        if addr_norm == obj_addr:
            coords_elem = offer.find("coordinates")
            if coords_elem is not None:
                try:
                    lat = float(coords_elem.get("lat", "0"))
                    lon = float(coords_elem.get("lon", "0"))
                    if lat != 0.0 or lon != 0.0:
                        return lat, lon
                except:
                    pass

    return 0.0, 0.0


# --- MAIN UPDATE LOOP ---
for offer in main_feed.findall(".//offer"):
    address_elem = offer.find("param[@name='Адрес']")
    if address_elem is None:
        continue

    address_text = address_elem.text or ""

    coords_elem = offer.find("coordinates")

    lat = lon = 0.0

    if coords_elem is not None:
        try:
            lat = float(coords_elem.get("lat", "0"))
            lon = float(coords_elem.get("lon", "0"))
        except:
            lat = lon = 0.0

    # --- FIX: убрали "Ярославль in address" (это ломало всё) ---
    if lat == 0.0 or lon == 0.0:
        lat_aux, lon_aux = get_coords_from_aux(address_text, aux_feed)

        if lat_aux != 0.0 or lon_aux != 0.0:
            lat, lon = lat_aux, lon_aux
        else:
            lat, lon = resolve_coordinates(address_text)

        if coords_elem is None:
            coords_elem = etree.SubElement(offer, "coordinates")

        coords_elem.set("lat", f"{lat:.6f}")
        coords_elem.set("lon", f"{lon:.6f}")

    # --- OFFICE LOGIC ---
    agent = offer.find("param[@name='Имя агента']")
    office_val = (
        "Буй"
        if agent is not None and agent.text in agents_bui
        else "Ярославль"
    )

    office_elem = offer.find("param[@name='Офис']")
    if office_elem is None:
        office_elem = etree.SubElement(offer, "param", name="Офис")

    office_elem.text = office_val


# --- developer flats ---
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
    etree.SubElement(offer, "param", name="Комнат").text = rooms
    etree.SubElement(offer, "param", name="Площадь Дома").text = total_area
    etree.SubElement(offer, "param", name="Жилая площадь").text = flat.findtext("LivingArea") or ""
    etree.SubElement(offer, "param", name="Площадь кухни").text = flat.findtext("KitchenArea") or ""
    etree.SubElement(offer, "param", name="Этаж").text = flat.findtext("FloorNumber") or ""
    etree.SubElement(offer, "param", name="Балкон").text = flat.findtext("BalconiesCount") or ""
    etree.SubElement(offer, "param", name="Парковка").text = flat.findtext("Building/Parking/Type") or ""
    etree.SubElement(offer, "param", name="Адрес").text = flat.findtext("Address") or ""

    # coords
    lat = float(flat.findtext("Coordinates/Lat") or "0")
    lon = float(flat.findtext("Coordinates/Lng") or "0")

    if lat == 0.0 or lon == 0.0:
        lat, lon = resolve_coordinates(flat.findtext("Address") or "")

    coords = etree.SubElement(offer, "coordinates")
    coords.set("lat", f"{lat:.6f}")
    coords.set("lon", f"{lon:.6f}")

    # photos
    layout_photo = flat.findtext("LayoutPhoto/FullUrl")
    if layout_photo:
        etree.SubElement(offer, "picture").text = layout_photo

    for photo in flat.findall("Photos/PhotoSchema"):
        url = photo.findtext("FullUrl")
        if url:
            etree.SubElement(offer, "picture").text = url

    etree.SubElement(offer, "param", name="Офис").text = "Ярославль"

    return offer


# --- merge offers ---
all_offers = []
all_offers.extend(main_feed.findall(".//offer"))
all_offers.extend([map_developer_flat(f, "Ин Парк") for f in in_park_feed.findall(".//object")])
all_offers.extend([map_developer_flat(f, "ЖК Новое Брагино") for f in novo_br_feed.findall(".//object")])


# --- XML build ---
shop = etree.Element("shop")
etree.SubElement(shop, "name")
etree.SubElement(shop, "company")
etree.SubElement(shop, "url")

curr = etree.SubElement(shop, "currencies")
etree.SubElement(curr, "currency", id="RUR", rate="1")

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

offers_root = etree.SubElement(shop, "offers")

for offer in all_offers:
    offers_root.append(offer)

tree = etree.ElementTree(shop)
tree.write("feed_final.xml", encoding="utf-8", xml_declaration=True, pretty_print=True)


# --- save cache ---
with open(CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(geo_cache, f, ensure_ascii=False, indent=2)

print("feed_final.xml создан успешно, геокодинг исправлен")
