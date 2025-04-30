from pydantic import BaseModel
from typing import Optional


class NHSInfo(BaseModel):
    age: int
    gender: str
    date_of_treatment: str
    health_issue: str


class RegisterRequest(BaseModel):
    name: str
    password: str
    nhsNumber: str


class LoginRequest(BaseModel):
    nhsNumber: str
    password: str
