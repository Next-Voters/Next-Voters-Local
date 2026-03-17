from pydantic import BaseModel


class BackgroundSubmitRequest(BaseModel):
    city: str


class BackgroundSubmitResponse(BaseModel):
    task_id: str
    status: str


class BackgroundStatusResponse(BaseModel):
    task_id: str
    status: str
    result: str | None = None
    error: str | None = None
