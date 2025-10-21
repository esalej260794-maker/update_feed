import requests
import xml.etree.ElementTree as ET
from geopy.geocoders import Nominatim
from time import sleep

# Ссылки на фиды
feeds = {
    "crm": "https://progress.vtcrm.ru/xmlgen/WebsiteYMLFeed.xml",
    "inpark": "https://progress.vtcrm.ru/xmlgen/CianinparkFeed.xml",
    "bragino": "https://idalite.ru/feed/26235f5e-76ef-4108-8e3e-82950637df0b"
}

# Инициализация геокодера
geolocator = Nominatim(user_agent="my_feed_bot")

# Создание корня нового YML
yml_root = ET.Element("yml_catalog", date="2025-10-21 06:50")
shop = ET.SubElement(yml_root, "shop")
categories = ET.SubElement(shop, "categories")
offers = ET.SubElement(shop, "offers")

# Категории (пример)
category_map = {
    "newBuildingFlatSale": 101,  # новостройки
    "Квартиры": 100,
    # добавьте остальные соответствия
}

# Материалы стен
material_map = {
    "monolith": "Монолит",
    "brick": "Кирпич",
    "panel": "Панель",
    "wood": "Дерево"
}

def get_coordinates(address):
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            return location.latitude, location.longitude
    except:
        return None, None
    return None, None

def process_feed(url, source_name):
    resp = requests.get(url)
    root = ET.fromstring(resp.content)
    
    # Пример обработки INPARK и Bragino, для CRM нужно подстроить под теги
    for obj in root.findall(".//object") + root.findall(".//offer"):
        offer_id = obj.findtext("ExternalId") or obj.get("id") or "0"
        offer_elem = ET.SubElement(offers, "offer", id=offer_id)
        
        # Название ЖК
        name = obj.findtext(".//JKSchema/Name") or obj.findtext("Name") or source_name
        ET.SubElement(offer_elem, "name").text = name
        
        # Адрес
        address = obj.findtext("Address") or obj.findtext("param[@name='Адрес']")
        ET.SubElement(offer_elem, "param", name="Адрес").text = address
        
        # Категория
        cat = obj.findtext("Category") or "Квартиры"
        ET.SubElement(offer_elem, "categoryId").text = str(category_map.get(cat, 100))
        
        # Материал стен
        material = obj.findtext("MaterialType") or "unknown"
        ET.SubElement(offer_elem, "param", name="Материал стен").text = material_map.get(material.lower(), material)
        
        # Цена
        price = obj.findtext(".//BargainTerms/Price") or obj.findtext("price") or "0"
        ET.SubElement(offer_elem, "price").text = price
        
        # Описание
        desc = obj.findtext("Description") or ""
        ET.SubElement(offer_elem, "description").text = desc
        
        # Координаты
        lat = obj.findtext(".//Coordinates/Lat")
        lng = obj.findtext(".//Coordinates/Lng")
        if not lat or not lng:
            lat, lng = get_coordinates(address)
            sleep(1)  # чтобы не забанили геокодер
        coord_elem = ET.SubElement(offer_elem, "coordinates")
        coord_elem.set("lat", str(lat) if lat else "0")
        coord_elem.set("lon", str(lng) if lng else "0")
        
        # Примеры фото
        photos = obj.findall(".//Photos/PhotoSchema/FullUrl") + obj.findall("picture")
        for p in photos:
            ET.SubElement(offer_elem, "picture").text = p.text if hasattr(p, "text") else str(p)

# Обработка всех фидов
process_feed(feeds["crm"], "CRM")
process_feed(feeds["inpark"], "ИН ПАРК")
process_feed(feeds["bragino"], "Новое Брагино")

# Сохранение итогового feed_final.xml
tree = ET.ElementTree(yml_root)
tree.write("feed_final.xml", encoding="utf-8", xml_declaration=True)
print("feed_final.xml создан успешно!")
