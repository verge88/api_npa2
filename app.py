from fastapi import FastAPI, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from .models import DocumentType, Document, DocumentDetail, SearchResponse
from .scraper import MeganormScraper
from .database import get_db, create_tables, DocumentTypeDB, DocumentDB
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(
    title="Meganorm API",
    description="API для извлечения документов по пожарной безопасности с сайта meganorm.ru",
    version="1.0.0"
)

# Создаем таблицы при запуске
create_tables()

scraper = MeganormScraper()
executor = ThreadPoolExecutor(max_workers=4)


@app.get("/")
async def root():
    return {"message": "Meganorm API - система извлечения документов по пожарной безопасности"}


@app.get("/document-types", response_model=List[DocumentType])
async def get_document_types(db: Session = Depends(get_db)):
    """Получить все типы документов"""

    # Проверяем, есть ли данные в БД
    db_types = db.query(DocumentTypeDB).all()

    if not db_types:
        # Если нет данных в БД, получаем с сайта
        loop = asyncio.get_event_loop()
        types_data = await loop.run_in_executor(executor, scraper.get_document_types)

        # Сохраняем в БД
        for type_data in types_data:
            db_type = DocumentTypeDB(
                name=type_data['name'],
                url=type_data['url']
            )
            db.add(db_type)

        db.commit()
        db_types = db.query(DocumentTypeDB).all()

    return [
        DocumentType(
            name=db_type.name,
            url=db_type.url,
            count=db_type.count
        )
        for db_type in db_types
    ]


@app.get("/documents/{doc_type}", response_model=List[Document])
async def get_documents_by_type(
        doc_type: str,
        page: int = Query(0, ge=0, description="Номер страницы"),
        db: Session = Depends(get_db)
):
    """Получить документы определенного типа"""

    # Находим тип документа в БД
    db_type = db.query(DocumentTypeDB).filter(DocumentTypeDB.name.ilike(f"%{doc_type}%")).first()

    if not db_type:
        raise HTTPException(status_code=404, detail="Тип документа не найден")

    # Получаем документы с сайта
    loop = asyncio.get_event_loop()
    documents_data = await loop.run_in_executor(
        executor,
        scraper.get_documents_by_type,
        db_type.url,
        page
    )

    documents = []
    for doc_data in documents_data:
        # Проверяем, есть ли документ в БД
        db_doc = db.query(DocumentDB).filter(DocumentDB.url == doc_data['url']).first()

        if not db_doc:
            # Сохраняем новый документ
            db_doc = DocumentDB(
                title=doc_data['title'],
                url=doc_data['url'],
                doc_type=db_type.name,
                date_published=doc_data.get('date_published'),
                number=doc_data.get('number')
            )
            db.add(db_doc)

        documents.append(Document(
            title=doc_data['title'],
            url=doc_data['url'],
            doc_type=db_type.name,
            date_published=doc_data.get('date_published'),
            number=doc_data.get('number')
        ))

    db.commit()
    return documents


@app.get("/document", response_model=DocumentDetail)
async def get_document_content(
        url: str = Query(..., description="URL документа"),
        db: Session = Depends(get_db)
):
    """Получить полное содержимое документа"""

    # Проверяем, есть ли документ в БД с контентом
    db_doc = db.query(DocumentDB).filter(DocumentDB.url == url).first()

    if db_doc and db_doc.content:
        sections = json.loads(db_doc.sections) if db_doc.sections else []
        return DocumentDetail(
            title=db_doc.title,
            url=db_doc.url,
            doc_type=db_doc.doc_type,
            date_published=db_doc.date_published,
            number=db_doc.number,
            content=db_doc.content,
            sections=sections
        )

    # Получаем контент с сайта
    loop = asyncio.get_event_loop()
    content_data = await loop.run_in_executor(executor, scraper.get_document_content, url)

    if not content_data['content']:
        raise HTTPException(status_code=404, detail="Документ не найден или недоступен")

    # Обновляем или создаем запись в БД
    if db_doc:
        db_doc.content = content_data['content']
        db_doc.sections = json.dumps(content_data['sections'])
        if not db_doc.title:
            db_doc.title = content_data['title']
    else:
        db_doc = DocumentDB(
            title=content_data['title'],
            url=url,
            doc_type="Неизвестно",
            content=content_data['content'],
            sections=json.dumps(content_data['sections'])
        )
        db.add(db_doc)

    db.commit()

    return DocumentDetail(
        title=content_data['title'],
        url=url,
        doc_type=db_doc.doc_type,
        date_published=db_doc.date_published,
        number=db_doc.number,
        content=content_data['content'],
        sections=content_data['sections']
    )


@app.get("/search", response_model=SearchResponse)
async def search_documents(
        q: str = Query(..., description="Поисковый запрос"),
        doc_type: Optional[str] = Query(None, description="Фильтр по типу документа"),
        page: int = Query(1, ge=1, description="Номер страницы"),
        per_page: int = Query(10, ge=1, le=100, description="Количество результатов на странице"),
        db: Session = Depends(get_db)
):
    """Поиск документов"""

    # Поиск в БД
    query = db.query(DocumentDB).filter(DocumentDB.title.ilike(f"%{q}%"))

    if doc_type:
        query = query.filter(DocumentDB.doc_type.ilike(f"%{doc_type}%"))

    total = query.count()
    documents_db = query.offset((page - 1) * per_page).limit(per_page).all()

    documents = [
        Document(
            title=doc.title,
            url=doc.url,
            doc_type=doc.doc_type,
            date_published=doc.date_published,
            number=doc.number,
            content=doc.content[:200] + "..." if doc.content and len(doc.content) > 200 else doc.content
        )
        for doc in documents_db
    ]

    # Если результатов мало, дополнительно ищем на сайте
    if len(documents) < per_page:
        loop = asyncio.get_event_loop()
        online_docs = await loop.run_in_executor(
            executor,
            scraper.search_documents,
            q,
            doc_type
        )

        # Добавляем новые документы, которых нет в БД
        for doc_data in online_docs[:per_page - len(documents)]:
            if not any(d.url == doc_data['url'] for d in documents):
                documents.append(Document(
                    title=doc_data['title'],
                    url=doc_data['url'],
                    doc_type=doc_data.get('doc_type', 'Неизвестно'),
                    date_published=doc_data.get('date_published'),
                    number=doc_data.get('number')
                ))

    return SearchResponse(
        documents=documents,
        total=max(total, len(documents)),
        page=page,
        per_page=per_page
    )


@app.post("/refresh-types")
async def refresh_document_types(db: Session = Depends(get_db)):
    """Обновить список типов документов"""

    loop = asyncio.get_event_loop()
    types_data = await loop.run_in_executor(executor, scraper.get_document_types)

    # Очищаем старые данные
    db.query(DocumentTypeDB).delete()

    # Добавляем новые
    for type_data in types_data:
        db_type = DocumentTypeDB(
            name=type_data['name'],
            url=type_data['url']
        )
        db.add(db_type)

    db.commit()

    return {"message": f"Обновлено {len(types_data)} типов документов"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
