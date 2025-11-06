"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.
Class name -> collection name (lowercased)

App entities:
- Student
- Attendance
- Agenda
- Grade
- AdminUser (for simple auth config)
"""
from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt

class Student(BaseModel):
    name: str = Field(..., description="Full name of student")
    className: str = Field(..., description="Class/grade, e.g., 5A")

class Attendance(BaseModel):
    student_id: str = Field(..., description="Reference to student _id as string")
    date: dt.date = Field(..., description="Attendance date (YYYY-MM-DD)")
    status: str = Field(..., description="Hadir | Alfa | Izin | Sakit")

class Agenda(BaseModel):
    title: str = Field(..., description="Agenda title")
    date: dt.date = Field(..., description="Agenda date")
    note: Optional[str] = Field(None, description="Optional note")

class Grade(BaseModel):
    student_id: str = Field(..., description="Reference to student _id as string")
    subject: str = Field(..., description="Subject name")
    score: float = Field(..., ge=0, le=100, description="Score 0-100")
    date: Optional[dt.date] = Field(None, description="Date of assessment")

class AdminUser(BaseModel):
    username: str
    password: str
    is_active: bool = True
