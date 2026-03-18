"""Pydantic models for NV Local API request and response schemas.

This module defines the data models used by the FastAPI server for handling
background task submissions and status queries.

Classes:
    BackgroundSubmitRequest: Request model for submitting a city analysis task.
    BackgroundSubmitResponse: Response model for task submission.
    BackgroundStatusResponse: Response model for task status queries.
"""

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
