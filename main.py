
#!/usr/bin/env python3
"""RSS no oficial de PiQ Markets Business & Corporate."""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

SOURCE = 'https://piqmarkets.com/business-corporate'
FEED_URL = 'https://plis2100.github.io/piqmarkets-business-corporate/feed.xml'
ARCHIVE = 'articles.json'
OUTPUT = 'feed.xml'
MAX_ITEMS = 400


def clean(value):
    return re.sub(r'\s+', ' ', value or '').strip()


def canonical(url):
    p = urlsplit(urljoin(SOURCE, url))
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/'), '', ''))


def fetch_articles():
    response = requests.get(SOURCE, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; PiQBusinessRSS/1.0; +https://github.com/plis2100/piqmarkets-business-corporate)',
        'Accept': 'text/html,application/xhtml+xml',
    }, timeout=35)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    results = {}
    for link in soup.select('a[href]'):
        href = link.get('href', '')
        url = canonical(href)
        parsed = urlsplit(url)
        if parsed.netloc not in ('piqmarkets.com', 'www.piqmarkets.com'):
            continue
        if not parsed.path.startswith('/story/'):
            continue
        title = clean(link.get_text(' ', strip=True))
        if len(title) < 12:
            parent = link.find_parent(['h1', 'h2', 'h3'])
            if parent:
                title = clean(parent.get_text(' ', strip=True))
        if len(title) < 12:
            continue
        # Una URL de historia equivale a un único artículo, aunque haya varios enlaces.
        results[url] = {'title': title, 'link': url}
    return list(results.values())


def load_archive():
    if not os.path.exists(ARCHIVE):
        return {}
    with open(ARCHIVE, 'r', encoding='utf-8') as file:
        raw = json.load(file)
    if not isinstance(raw, dict):
        raise ValueError('El archivo de historial debe ser un objeto JSON.')
    return raw


def save_archive(items):
    with open(ARCHIVE, 'w', encoding='utf-8') as file:
        json.dump(items, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write('\n')


def build_rss(items):
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    for tag, value in (
        ('title', 'PiQ Markets | Business & Corporate'),
        ('link', SOURCE),
        ('description', 'Titulares de Business & Corporate de PiQ Markets (RSS no oficial).'),
        ('language', 'en'),
        ('lastBuildDate', format_datetime(datetime.now(timezone.utc))),
        ('ttl', '60'),
    ):
        ET.SubElement(channel, tag).text = value
    ordered = sorted(items.values(), key=lambda x: x['first_seen'], reverse=True)
    for entry in ordered[:MAX_ITEMS]:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = entry['title']
        ET.SubElement(item, 'link').text = entry['link']
        ET.SubElement(item, 'guid', {'isPermaLink': 'true'}).text = entry['link']
        when = datetime.fromisoformat(entry['first_seen'])
        ET.SubElement(item, 'pubDate').text = format_datetime(when)
    ET.indent(rss, space='  ')
    ET.ElementTree(rss).write(OUTPUT, encoding='utf-8', xml_declaration=True)


def main():
    articles = fetch_articles()
    if not articles:
        raise RuntimeError('No se encontraron enlaces /story/ en el HTML. No se sobrescribe el RSS; la página puede haber cambiado o cargar noticias con JavaScript.')
    archive = load_archive()
    now = datetime.now(timezone.utc).isoformat()
    new = 0
    for article in articles:
        key = hashlib.sha256(article['link'].encode('utf-8')).hexdigest()
        if key not in archive:
            archive[key] = {**article, 'first_seen': now}
            new += 1
        # No cambiamos el título ni la fecha de artículos ya publicados.
    archive = dict(sorted(archive.items(), key=lambda x: x[1]['first_seen'], reverse=True)[:MAX_ITEMS])
    save_archive(archive)
    build_rss(archive)
    print(f'Encontradas: {len(articles)} | Nuevas: {new} | En RSS: {len(archive)}')


if __name__ == '__main__':
    main()
