import requests
from bs4 import BeautifulSoup
from typing import List, Optional
import re
import time
from urllib.parse import urljoin, urlparse
from models import Document, DocumentType, ScrapingResult

class MeganormScraper:
    def __init__(self):
        self.base_url = "https://meganorm.ru"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Получить и парсить страницу"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"Ошибка при загрузке {url}: {e}")
            return None
    
    def get_document_types(self) -> ScrapingResult:
        """Извлечь все типы документов с главной страницы"""
        main_url = "https://meganorm.ru/mega_doc/fire/fire.html"
        soup = self.get_page(main_url)
        
        if not soup:
            return ScrapingResult(success=False, data=[], error="Не удалось загрузить главную страницу")
        
        document_types = []
        
        try:
            # Поиск ссылок на типы документов
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href')
                if not href or not href.startswith('/mega_doc/fire/'):
                    continue
                
                # Пропускаем основную страницу и якорные ссылки
                if href.endswith('fire.html') or '#' in href:
                    continue
                
                title = link.get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                
                full_url = urljoin(self.base_url, href)
                
                # Извлекаем тип документа из URL
                doc_type = self._extract_doc_type_from_url(href)
                
                document_types.append(DocumentType(
                    name=title,
                    url=full_url,
                    description=doc_type
                ).to_dict())
            
            # Удаляем дубликаты
            unique_types = []
            seen_urls = set()
            
            for doc_type in document_types:
                if doc_type['url'] not in seen_urls:
                    seen_urls.add(doc_type['url'])
                    unique_types.append(doc_type)
            
            return ScrapingResult(
                success=True,
                data=unique_types,
                total_count=len(unique_types)
            )
            
        except Exception as e:
            return ScrapingResult(success=False, data=[], error=f"Ошибка парсинга: {str(e)}")
    
    def get_documents_by_type(self, type_url: str, limit: int = 50) -> ScrapingResult:
        """Получить список документов определенного типа"""
        soup = self.get_page(type_url)
        
        if not soup:
            return ScrapingResult(success=False, data=[], error="Не удалось загрузить страницу типа документов")
        
        documents = []
        
        try:
            # Поиск ссылок на документы
            doc_links = soup.find_all('a', href=True)
            
            for link in doc_links:
                href = link.get('href')
                if not href or not self._is_document_link(href):
                    continue
                
                if len(documents) >= limit:
                    break
                
                title = link.get_text(strip=True)
                if not title:
                    continue
                
                full_url = urljoin(self.base_url, href)
                doc_type = self._extract_doc_type_from_url(href)
                
                # Попытка извлечь дату и номер из названия
                date, number = self._extract_date_and_number(title)
                
                documents.append(Document(
                    title=title,
                    url=full_url,
                    doc_type=doc_type,
                    date=date,
                    number=number
                ).to_dict())
            
            return ScrapingResult(
                success=True,
                data=documents,
                total_count=len(documents)
            )
            
        except Exception as e:
            return ScrapingResult(success=False, data=[], error=f"Ошибка парсинга документов: {str(e)}")
    
    def get_document_content(self, doc_url: str) -> ScrapingResult:
        """Получить полное содержимое документа"""
        soup = self.get_page(doc_url)
        
        if not soup:
            return ScrapingResult(success=False, data=[], error="Не удалось загрузить документ")
        
        try:
            # Извлечение заголовка
            title = ""
            title_elem = soup.find('h1') or soup.find('title')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # Извлечение основного содержимого
            content = ""
            
            # Попытка найти основной контент различными способами
            content_selectors = [
                'div.content',
                'div.document',
                'div.main-content',
                'article',
                'main',
                'div#content'
            ]
            
            content_elem = None
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    break
            
            if not content_elem:
                # Если специальный контейнер не найден, берем весь body
                content_elem = soup.find('body')
            
            if content_elem:
                # Удаляем ненужные элементы
                for elem in content_elem.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    elem.decompose()
                
                content = content_elem.get_text(separator='\n', strip=True)
            
            # Извлечение метаданных
            date, number = self._extract_date_and_number(title)
            doc_type = self._extract_doc_type_from_url(doc_url)
            
            document = Document(
                title=title,
                url=doc_url,
                doc_type=doc_type,
                date=date,
                number=number,
                content=content
            )
            
            return ScrapingResult(
                success=True,
                data=[document.to_dict()],
                total_count=1
            )
            
        except Exception as e:
            return ScrapingResult(success=False, data=[], error=f"Ошибка извлечения содержимого: {str(e)}")
    
    def search_documents(self, query: str, doc_type: str = None, limit: int = 20) -> ScrapingResult:
        """Поиск документов по ключевому слову"""
        try:
            # Сначала получаем все типы документов
            types_result = self.get_document_types()
            if not types_result.success:
                return types_result
            
            all_documents = []
            
            for doc_type_info in types_result.data:
                if doc_type and doc_type.lower() not in doc_type_info['name'].lower():
                    continue
                
                docs_result = self.get_documents_by_type(doc_type_info['url'], limit=100)
                if docs_result.success:
                    # Фильтруем по запросу
                    for doc in docs_result.data:
                        if query.lower() in doc['title'].lower():
                            all_documents.append(doc)
                            if len(all_documents) >= limit:
                                break
                
                if len(all_documents) >= limit:
                    break
                
                time.sleep(0.5)  # Задержка между запросами
            
            return ScrapingResult(
                success=True,
                data=all_documents,
                total_count=len(all_documents)
            )
            
        except Exception as e:
            return ScrapingResult(success=False, data=[], error=f"Ошибка поиска: {str(e)}")
    
    def _extract_doc_type_from_url(self, url: str) -> str:
        """Извлечь тип документа из URL"""
        path_parts = url.split('/')
        for part in path_parts:
            if 'zakon' in part:
                return 'Закон'
            elif 'postanovlen' in part:
                return 'Постановление'
            elif 'gost' in part:
                return 'ГОСТ'
            elif 'ppb' in part:
                return 'ППБ'
            elif 'snip' in part:
                return 'СНиП'
            elif 'sp' in part:
                return 'СП'
        return 'Документ'
    
    def _is_document_link(self, href: str) -> bool:
        """Проверить, является ли ссылка ссылкой на документ"""
        return (href.startswith('/mega_doc/fire/') and 
                not href.endswith('.html') or 
                'zakon' in href or 'gost' in href or 'postanovlen' in href)
    
    def _extract_date_and_number(self, title: str) -> tuple:
        """Извлечь дату и номер из названия документа"""
        date_pattern = r'(\d{1,2}[./]\d{1,2}[./]\d{4})'
        number_pattern = r'№?\s*(\d+[\w\-]*)'
        
        date_match = re.search(date_pattern, title)
        number_match = re.search(number_pattern, title)
        
        date = date_match.group(1) if date_match else None
        number = number_match.group(1) if number_match else None
        
        return date, number
