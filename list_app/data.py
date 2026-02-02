from pydantic import BaseModel


class ApplicationData(BaseModel):
    name: str
    url: str
    description: str
    tags: set[str]
