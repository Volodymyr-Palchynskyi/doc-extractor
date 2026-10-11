from typing import Literal

from pydantic import BaseModel


class AppInfo(BaseModel):
    mode: Literal["gemini", "demo"]
    max_upload_mb: int
    max_pages: int
    document_ttl_s: int


class SampleInfo(BaseModel):
    id: str
    title: str
    description: str
    file_name: str
