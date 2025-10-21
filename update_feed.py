import requests
from lxml import etree
from geopy.geocoders import Nominatim
import time

# --- Настройка геокодера ---
geolocator = Nominatim(user_agent="real_estate_feed")

def geocode_address(address):
    try:
        location = geolocator.geocode(address + ", Россия")
        time.sleep(1)  # ограничение запросов
        if location:
            return location.latitude, location.longitude
    except Exception as e:
        print("Ошибка геокодирования:", address, e)
    return 0.0, 0.0

# --- Ссылки на фиды ---
feeds = {
    "main": "https://progress.vtcrm.ru/xmlgen/WebsiteYMLFeed.xml",
    "in_park": "https://progress.vtcrm.ru/xmlgen/CianinparkFeed.xml",
    "novo_br": "https://idalite.ru/feed/26235f5e-76ef-4108-8e3e-82950637df0b"
}

# --- Загрузка фида ---
def load_feed(url):
    r = requests.get(url)
    return etree.fromstring(r.content)

main_feed = load_feed(feeds["main"])
in_park_feed = load_feed(feeds["in_park"])
novo_br_feed = load_feed(feeds["novo_br"])

# --- Обработка основного фида ---
for offer in main_feed.findall(".//offer"):
    # Адрес
    address_elem = offer.find(".//param[@name='Адрес']")
    if address_elem is not None:
        address_text = address_elem.text
        lat_elem = offer.find("coordinates[@lat]")
        lon_elem = offer.find("coordinates[@lon]")
        if lat_elem is None or lat_elem.get("lat") in ("0", None):
            lat, lon = geocode_address(address_text)
            if offer.find("coordinates") is None:
                coords = etree.SubElement(offer, "coordinates")
            else:
                coords = offer.find("coordinates")
            coords.set("lat", f"{lat:.6f}")
            coords.set("lon", f"{lon:.6f}")
    # Офис
    agent = offer.find(".//param[@name='Имя агента']")
    if agent is not None and agent.text in ["Евгения Серова","Виктория Набатова","Ольга Торопова","Наталья Квасова"]:
        office_val = "Буй"
    else:
        office_val = "Ярославль"
    office_elem = offer.find(".//param[@name='Офис']")
    if office_elem is None:
        office_elem = etree.SubElement(offer, "param", name="Офис")
    office_elem.text = office_val

# --- Обработка фидов застройщиков ---
def map_in_park_flat(flat):
    offer = etree.Element("offer")
    # Категория
    etree.SubElement(offer, "categoryId").text = "101"
    # Name
    rooms = flat.findtext(".//FlatRoomsCount") or "0"
    total_area = flat.findtext(".//TotalArea") or "0"
    jkschema_name = flat.findtext(".//JKSchema/Name") or "Ин Парк"
    offer_name = f"{rooms}-к, {total_area} кв.м, ЖК {jkschema_name}"
    etree.SubElement(offer, "name").text = offer_name
    # Price
    price = flat.findtext(".//BargainTerms/Price") or "0"
    etree.SubElement(offer, "price").text = price
    # Description
    desc = flat.findtext(".//Description") or ""
    etree.SubElement(offer, "description").text = desc
    # Материал стен
    material = flat.findtext(".//MaterialType") or "unknown"
    etree.SubElement(offer, "param", name="Материал стен").text = material
    # Площади, комнаты, этаж
    etree.SubElement(offer, "param", name="Комнат").text = flat.findtext(".//FlatRoomsCount") or ""
    etree.SubElement(offer, "param", name="Площадь Дома").text = flat.findtext(".//TotalArea") or ""
    etree.SubElement(offer, "param", name="Жилая площадь").text = flat.findtext(".//LivingArea") or ""
    etree.SubElement(offer, "param", name="Площадь кухни").text = flat.findtext(".//KitchenArea") or ""
    etree.SubElement(offer, "param", name="Этаж").text = flat.findtext(".//FloorNumber") or ""
    etree.SubElement(offer, "param", name="Балкон").text = flat.findtext(".//BalconiesCount") or ""
    etree.SubElement(offer, "param", name="Парковка").text = flat.findtext(".//Parking/Type") or ""
    # Адрес
    addr = flat.findtext(".//Address") or ""
    etree.SubElement(offer, "param", name="Адрес").text = addr
    # Координаты
    lat = flat.findtext(".//Coordinates/Lat")
    lon = flat.findtext(".//Coordinates/Lng")
    if not lat or lat=="0":
        lat, lon = geocode_address(addr)
    coords = etree.SubElement(offer, "coordinates")
    coords.set("lat", f"{float(lat):.6f}")
    coords.set("lon", f"{float(lon):.6f}")
    # Офис всегда Ярославль
    etree.SubElement(offer, "param", name="Офис").text = "Ярославль"
    return offer

# --- Собираем все flat ---
all_offers = []
for flat in in_park_feed.findall(".//Flat"):
    all_offers.append(map_in_park_flat(flat))

for flat in novo_br_feed.findall(".//Flat"):
    all_offers.append(map_in_park_flat(flat))

# --- Добавляем основной фид ---
for offer in main_feed.findall(".//offer"):
    all_offers.append(offer)

# --- Финальный XML ---
root = etree.Element("offers")
for offer in all_offers:
    root.append(offer)

tree = etree.ElementTree(root)
tree.write("feed_final.xml", encoding="utf-8", xml_declaration=True, pretty_print=True)
print("feed_final.xml создан успешно")


