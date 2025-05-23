import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional
import time
from urllib.parse import urljoin, urlparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MeganormScraper:
    def __init__(self):
        self.base_url = "https://meganorm.ru"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def get_document_types(self) -> List[Dict[str, str]]:
        """Извлекает все типы документов с главной страницы"""
        url = "https://meganorm.ru/mega_doc/fire/fire.html"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            document_types = []

            # Ищем все ссылки на типы документов
            links = soup.find_all('a', href=True)

            for link in links:
                href = link.get('href')
                text = link.get_text(strip=True)

                # Фильтруем ссылки на типы документов
                if href and '/mega_doc/fire/' in href and text:
                    # Исключаем ссылки на конкретные документы
                    if not any(x in href.lower() for x in ['#', '.html#', 'zakon/0/', 'gost/0/']):
                        if any(keyword in text.lower() for keyword in [
                            'закон', 'постановление', 'гост', 'снип', 'правила',
                            'требования', 'инструкция', 'стандарт', 'норма'
                        ]):
                            full_url = urljoin(self.base_url, href)
                            document_types.append({
                                'name': text,
                                'url': full_url
                            })

            # Удаляем дубликаты
            seen = set()
            unique_types = []
            for doc_type in document_types:
                if doc_type['url'] not in seen:
                    seen.add(doc_type['url'])
                    unique_types.append(doc_type)

            logger.info(f"Найдено {len(unique_types)} типов документов")
            return unique_types

        except Exception as e:
            logger.error(f"Ошибка при получении типов документов: {e}")
            return []

    def get_documents_by_type(self, type_url: str, page: int = 0) -> List[Dict[str, str]]:
        """Извлекает список документов определенного типа"""
        try:
            # Если это не первая страница, добавляем номер страницы к URL
            if page > 0:
                if type_url.endswith('.html'):
                    type_url = type_url.replace('.html', f'_{page}.html')
                else:
                    type_url = f"{type_url}_{page}.html"

            response = self.session.get(type_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            documents = []

            # Ищем ссылки на документы
            links = soup.find_all('a', href=True)

            for link in links:
                href = link.get('href')
                text = link.get_text(strip=True)

                if href and text and len(text) > 10:
                    # Проверяем, что это ссылка на документ
                    if '/zakon/0/' in href or '/gost/0/' in href or 'postanovlenie' in href.lower():
                        full_url = urljoin(self.base_url, href)

                        # Извлекаем дату и номер из названия
                        date_match = re.search(r'от\s+(\d{2}[\._]\d{2}[\._]\d{4})', text)
                        number_match = re.search(r'[№N]\s*(\d+[-\w]*)', text)

                        documents.append({
                            'title': text,
                            'url': full_url,
                            'date_published': date_match.group(1).replace('_', '.') if date_match else None,
                            'number': number_match.group(1) if number_match else None
                        })

            logger.info(f"Найдено {len(documents)} документов на странице {page}")
            return documents

        except Exception as e:
            logger.error(f"Ошибка при получении документов: {e}")
            return []

    def get_document_content(self, document_url: str) -> Dict[str, any]:
        """Извлекает полное содержимое документа"""
        try:
            response = self.session.get(document_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Извлекаем заголовок
            title = ""
            title_elem = soup.find('h1') or soup.find('title')
            if title_elem:
                title = title_elem.get_text(strip=True)

            # Извлекаем основной контент
            content = ""
            content_div = soup.find('div', class_='content') or soup.find('div', id='content')

            if not content_div:
                # Если не найден основной контент, берем весь текст body
                content_div = soup.find('body')

            if content_div:
                # Удаляем скрипты и стили
                for script in content_div(["script", "style"]):
                    script.decompose()

                content = content_div.get_text(separator='\n', strip=True)

            # Извлекаем разделы/главы
            sections = []
            section_headers = soup.find_all(['h2', 'h3', 'h4'])
            for header in section_headers:
                section_text = header.get_text(strip=True)
                if section_text and len(section_text) > 3:
                    sections.append(section_text)

            return {
                'title': title,
                'content': content,
                'sections': sections[:20]  # Ограничиваем количество разделов
            }

        except Exception as e:
            logger.error(f"Ошибка при получении содержимого документа {document_url}: {e}")
            return {'title': '', 'content': '', 'sections': []}

    def search_documents(self, query: str, doc_type: str = None) -> List[Dict[str, str]]:
        """Поиск документов по запросу"""
        all_documents = []

        # Получаем типы документов
        document_types = self.get_document_types()

        for doc_type_info in document_types:
            if doc_type and doc_type.lower() not in doc_type_info['name'].lower():
                continue

            documents = self.get_documents_by_type(doc_type_info['url'])

            # Фильтруем по запросу
            for doc in documents:
                if query.lower() in doc['title'].lower():
                    doc['doc_type'] = doc_type_info['name']
                    all_documents.append(doc)

        return all_documents