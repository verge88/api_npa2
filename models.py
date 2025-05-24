from dataclasses import dataclass, asdict
from typing import List, Optional
from datetime import datetime

@dataclass
class Document:
    title: str
    url: str
    doc_type: str
    date: Optional[str] = None
    number: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class DocumentType:
    name: str
    url: str
    count: Optional[int] = None
    description: Optional[str] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class ScrapingResult:
    success: bool
    data: List[dict]
    error: Optional[str] = None
    total_count: int = 0
    
    def to_dict(self):
        return asdict(self)
