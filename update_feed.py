import requests
import xml.etree.ElementTree as ET
from geopy.geocoders import Nominatim

# --- Настройки ---
geolocator = Nominatim(user_agent="feed_geocoder")

# Ссылки на фиды
feeds = {
    "main": "https://progress.vtcrm.ru/xmlgen/WebsiteYMLFeed.xml",
    "inpark": "https://progress.vtcrm.ru/xmlgen/CianinparkFeed.xml",
    "novoe_bragino": "https://idalite.ru/feed/26235f5e-76ef-4108-8e3e-82950637df0b"
}

# --- Функции ---
def get_coordinates(address):
    try:
        loc = geolocator.geocode(address)
        if loc:
            return loc.latitude, loc.longitude
    except:
        return None, None
    return None, None

def parse_main_feed(url):
    r = requests.get(url)
    tree = ET.ElementTree(ET.fromstring(r.content))
    return tree

def parse_inpark_feed(url):
    r = requests.get(url)
    root = ET.fromstring(r.content)
    offers = []
    for obj in root.findall(".//object"):
        offer = {}
        offer['name'] = obj.findtext(".//JKSchema/Name") or "ИН ПАРК"
        offer['address'] = obj.findtext(".//Address")
        lat = obj.findtext(".//Coordinates/Lat")
        lng = obj.findtext(".//Coordinates/Lng")
        if lat and lng:
            offer['coordinates'] = (lat, lng)
        else:
            offer['coordinates'] = get_coordinates(offer['address'])
        offer['categoryId'] = "101"  # Новостройки
        material = obj.findtext(".//Building/MaterialType") or ""
        if material.lower() == "monolith":
            offer['material'] = "Монолит"
        else:
            offer['material'] = material
        price = obj.findtext(".//BargainTerms/Price")
        offer['price'] = price
        # можно добавить остальные поля по аналогии
        offers.append(offer)
    return offers

def parse_novoe_bragino_feed(url):
    r = requests.get(url)
    root = ET.fromstring(r.content)
    offers = []
    for obj in root.findall(".//object"):
        offer = {}
        offer['name'] = obj.findtext(".//JKSchema/Name") or "Новое Брагино"
        offer['address'] = obj.findtext(".//Address")
        lat = obj.findtext(".//Coordinates/Lat")
        lng = obj.findtext(".//Coordinates/Lng")
        if lat and lng:
            offer['coordinates'] = (lat, lng)
        else:
            offer['coordinates'] = get_coordinates(offer['address'])
        offer['categoryId'] = "101"  # Новостройки
        material = obj.findtext(".//Building/MaterialType") or ""
        if material.lower() == "monolith":
            offer['material'] = "Монолит"
        else:
            offer['material'] = material
        price = obj.findtext(".//BargainTerms/Price")
        offer['price'] = price
        offers.append(offer)
    return offers

def generate_feed(main_tree, additional_offers):
    shop = main_tree.find("shop")
    offers_el = shop.find("offers")
    # добавляем новые объекты
    for o in additional_offers:
        offer_el = ET.SubElement(offers_el, "offer", id="new_"+o['name'])
        ET.SubElement(offer_el, "name").text = o['name']
        ET.SubElement(offer_el, "categoryId").text = o['categoryId']
        ET.SubElement(offer_el, "price").text = str(o['price'] or 0)
        ET.SubElement(offer_el, "param", name="Материал стен").text = o['material']
        coords = ET.SubElement(offer_el, "coordinates")
        coords.set("lat", str(o['coordinates'][0]))
        coords.set("lon", str(o['coordinates'][1]))
        ET.SubElement(offer_el, "param", name="Адрес").text = o['address']
    main_tree.write("feed_final.xml", encoding="utf-8", xml_declaration=True)

# --- Основной код ---
main_tree = parse_main_feed(feeds['main'])
additional_offers = parse_inpark_feed(feeds['inpark']) + parse_novoe_bragino_feed(feeds['novoe_bragino'])
generate_feed(main_tree, additional_offers)
print("Feed updated successfully!")
