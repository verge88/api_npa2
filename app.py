import requests
from bs4 import BeautifulSoup
import re

def extract_document_types(url):
    """
    Извлекает типы документов со страницы meganorm.ru.

    Args:
        url (str): URL страницы, с которой нужно извлечь типы документов.

    Returns:
        list: Список строк с типами документов.
              Возвращает пустой список в случае ошибки.
    """
    document_types = []
    try:
        # Добавляем User-Agent, чтобы имитировать запрос от браузера
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Проверка на ошибки HTTP (4xx или 5xx)
        response.encoding = 'windows-1251' # Судя по сайту, используется эта кодировка
        soup = BeautifulSoup(response.text, 'html.parser')

        # Эмпирический поиск таблицы с типами документов.
        # На сайте https://meganorm.ru/mega_doc/fire/fire.html
        # типы документов представлены в таблице.
        # Каждый тип документа находится в первой ячейке <td> каждой строки <tr>.
        # Внутри ячейки может быть тег <a> или просто текст.

        # Попробуем найти все таблицы на странице
        tables = soup.find_all('table')

        # Предполагаем, что нужная таблица - это та, в которой есть строки,
        # и первая ячейка строки содержит текст, похожий на тип документа.
        # Это предположение, так как без точных классов или ID это сложно.
        # На основе анализа страницы (вручную), таблица с типами документов не имеет
        # явных уникальных идентификаторов, но содержит строки с двумя ячейками:
        # первая - тип документа, вторая - количество.

        # Ищем таблицу, которая, вероятно, содержит список документов.
        # Обычно такие таблицы имеют много строк.
        # Также можно ориентироваться на наличие ссылок в первой ячейке.
        
        # На странице есть несколько таблиц. Нужная нам таблица, судя по структуре,
        # содержит ссылки в первой ячейке и цифры во второй.
        # Попробуем найти таблицу, где строки содержат ссылки, ведущие на списки документов.
        
        # Обновленный подход: Ищем строки таблицы (tr) внутри основного контента.
        # Основной контент часто находится в div с id="content" или class="content"
        # На данном сайте, похоже, нет такого явного контейнера для основной таблицы.
        # Будем искать все строки таблиц и фильтровать их.

        # Простой подход: ищем все строки `<tr>` на странице.
        rows = soup.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 1: # Убедимся, что в строке есть хотя бы одна ячейка
                first_cell = cells[0]
                # Тип документа может быть текстом ячейки или текстом ссылки внутри ячейки
                link = first_cell.find('a')
                doc_type_text = ''
                if link and link.text.strip():
                    doc_type_text = link.text.strip()
                else:
                    doc_type_text = first_cell.text.strip()

                # Проверяем, что текст не пустой и не является заголовком таблицы типа "Тип документа"
                # и не является числом (на случай если попали на ячейку с количеством)
                if doc_type_text and not doc_type_text.isdigit() and doc_type_text.lower() != "тип документа":
                    # Удаляем возможное количество в скобках, например, " (123)"
                    doc_type_text = re.sub(r'\s*\(\d+\)$', '', doc_type_text).strip()
                    if doc_type_text and doc_type_text not in document_types: # Предотвращаем дубликаты
                         # Дополнительная проверка, чтобы отсеять нерелевантные строки,
                         # например, строки навигации или подвалы таблиц.
                         # Будем считать релевантными строки, где есть хотя бы одно слово с заглавной буквы
                         # или несколько слов. Это очень грубое предположение.
                        if re.search(r'[А-ЯЁ]', doc_type_text) or len(doc_type_text.split()) > 1:
                             document_types.append(doc_type_text)
        
        # Если первый метод не дал много результатов, попробуем найти ссылки с определенным путем
        if not document_types or len(document_types) < 10: # Если найдено мало типов, пробуем другой метод
            print("Первый метод не дал достаточно результатов, пробую альтернативный поиск по ссылкам...")
            document_types = [] # Очищаем для второго метода
            # Ищем ссылки, которые ведут на страницы категорий документов
            # Пример ссылки: /mega_doc/fire/federalnyj-zakon/federalnyj-zakon_0.html
            # Нас интересует часть "federalnyj-zakon" - это и есть тип
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                # Ищем ссылки, содержащие "/mega_doc/fire/" и не заканчивающиеся на ".html" (это могут быть сами документы)
                # а скорее категории, например, "/mega_doc/fire/zakon/"
                match = re.search(r'/mega_doc/fire/([^/]+)/$', href) # Заканчивается на /
                if not match:
                     match = re.search(r'/mega_doc/fire/([^/]+)/[^/]*_0\.html$', href) # Заканчивается на _0.html

                if match:
                    type_candidate = match.group(1)
                    # Преобразуем из транслита в более читаемый вид (если возможно и есть паттерны)
                    # Это сложно сделать без словаря, поэтому просто очистим
                    type_candidate_text = link.text.strip()
                    
                    if type_candidate_text and type_candidate_text not in document_types:
                        # Убираем возможное количество в скобках
                        type_candidate_text = re.sub(r'\s*\(\d+\)$', '', type_candidate_text).strip()
                        if type_candidate_text:
                             document_types.append(type_candidate_text)
            
            # Удаляем дубликаты, сохраняя порядок
            seen = set()
            document_types = [x for x in document_types if not (x in seen or seen.add(x))]


    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к URL {url}: {e}")
    except Exception as e:
        print(f"Произошла ошибка при обработке страницы: {e}")
    
    return document_types

if __name__ == '__main__':
    target_url = "https://meganorm.ru/mega_doc/fire/fire.html"
    print(f"Извлечение типов документов с {target_url}...\n")
    
    types = extract_document_types(target_url)
    
    if types:
        print("Найденные типы документов:")
        for i, doc_type in enumerate(types):
            print(f"{i+1}. {doc_type}")
    else:
        print("Не удалось извлечь типы документов.")

