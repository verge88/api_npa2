from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DocumentType(BaseModel):
    name: str
    url: str
    count: Optional[int] = None

class Document(BaseModel):
    title: str
    url: str
    doc_type: str
    date_published: Optional[str] = None
    number: Optional[str] = None
    content: Optional[str] = None

class DocumentDetail(BaseModel):
    title: str
    url: str
    doc_type: str
    date_published: Optional[str] = None
    number: Optional[str] = None
    content: str
    sections: List[str] = []

class SearchResponse(BaseModel):
    documents: List[Document]
    total: int
    page: int
    per_page: int