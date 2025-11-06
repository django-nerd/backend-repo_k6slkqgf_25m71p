import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
from bson import ObjectId
from io import StringIO
import csv
from database import db, create_document, get_documents
from schemas import (
    Student as StudentSchema,
    Attendance as AttendanceSchema,
    Agenda as AgendaSchema,
    Grade as GradeSchema,
    AdminUser as AdminUserSchema,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory session for demo login token
SESSIONS = set()

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str

@app.get("/")
def read_root():
    return {"message": "School Attendance API ready"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set"
            response["database_name"] = getattr(db, 'name', 'unknown')
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()[:10]
            except Exception as e:
                response["database"] = f"⚠️ Connected but error listing collections: {str(e)[:80]}"
        else:
            response["database"] = "❌ Database not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:120]}"
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# Schemas endpoint for viewer
@app.get("/schema")
def get_schema():
    from schemas import Student, Attendance, Agenda, Grade, AdminUser
    def model_fields(model):
        return {k: str(v.annotation) for k, v in model.model_fields.items()}
    return {
        "student": model_fields(Student),
        "attendance": model_fields(Attendance),
        "agenda": model_fields(Agenda),
        "grade": model_fields(Grade),
        "adminuser": model_fields(AdminUser),
    }

# Utility: convert Mongo docs

def serialize(doc):
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["_id"] = str(d["_id"])
    return d

# Students CRUD
@app.post("/students")
def create_student(payload: StudentSchema):
    _id = create_document("student", payload)
    return {"_id": _id}

@app.get("/students")
def list_students():
    docs = get_documents("student")
    return [serialize(d) for d in docs]

@app.put("/students/{student_id}")
def update_student(student_id: str, payload: StudentSchema):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    res = db["student"].update_one({"_id": ObjectId(student_id)}, {"$set": {**payload.model_dump()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"updated": True}

@app.delete("/students/{student_id}")
def delete_student(student_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    db["attendance"].delete_many({"student_id": student_id})
    db["grade"].delete_many({"student_id": student_id})
    res = db["student"].delete_one({"_id": ObjectId(student_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"deleted": True}

# Attendance
@app.post("/attendance")
def mark_attendance(payload: AttendanceSchema):
    # Upsert by student_id + date
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    data = payload.model_dump()
    db["attendance"].update_one(
        {"student_id": data["student_id"], "date": data["date"]},
        {"$set": data, "$setOnInsert": {"created_at": None}},
        upsert=True,
    )
    doc = db["attendance"].find_one({"student_id": data["student_id"], "date": data["date"]})
    return serialize(doc)

@app.get("/attendance")
def list_attendance(student_id: Optional[str] = None, on_date: Optional[date] = None, start_date: Optional[date] = None, end_date: Optional[date] = None):
    filt: dict = {}
    if student_id:
        filt["student_id"] = student_id
    if on_date:
        filt["date"] = on_date
    if start_date or end_date:
        rng = {}
        if start_date:
            rng["$gte"] = start_date
        if end_date:
            rng["$lte"] = end_date
        filt["date"] = rng
    docs = list(db["attendance"].find(filt)) if db else []
    return [serialize(d) for d in docs]

@app.get("/attendance/export")
def export_attendance_csv(start_date: Optional[date] = None, end_date: Optional[date] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    filt: dict = {}
    if start_date or end_date:
        rng = {}
        if start_date:
            rng["$gte"] = start_date
        if end_date:
            rng["$lte"] = end_date
        filt["date"] = rng
    rows = list(db["attendance"].find(filt))
    # Build CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["_id", "student_id", "date", "status"]) 
    for r in rows:
        writer.writerow([str(r.get("_id")), r.get("student_id"), str(r.get("date")), r.get("status")])
    csv_bytes = output.getvalue().encode("utf-8")
    return Response(content=csv_bytes, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=attendance.csv"
    })

@app.delete("/attendance/{attendance_id}")
def delete_attendance(attendance_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    res = db["attendance"].delete_one({"_id": ObjectId(attendance_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Attendance not found")
    return {"deleted": True}

# Agenda CRUD
@app.post("/agendas")
def create_agenda(payload: AgendaSchema):
    _id = create_document("agenda", payload)
    return {"_id": _id}

@app.get("/agendas")
def list_agendas():
    docs = get_documents("agenda")
    return [serialize(d) for d in docs]

@app.put("/agendas/{agenda_id}")
def update_agenda(agenda_id: str, payload: AgendaSchema):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    res = db["agenda"].update_one({"_id": ObjectId(agenda_id)}, {"$set": {**payload.model_dump()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Agenda not found")
    return {"updated": True}

@app.delete("/agendas/{agenda_id}")
def delete_agenda(agenda_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    res = db["agenda"].delete_one({"_id": ObjectId(agenda_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Agenda not found")
    return {"deleted": True}

# Grades CRUD (create/list/delete)
@app.post("/grades")
def add_grade(payload: GradeSchema):
    _id = create_document("grade", payload)
    return {"_id": _id}

@app.get("/grades")
def list_grades(student_id: Optional[str] = None):
    filt = {"student_id": student_id} if student_id else {}
    docs = get_documents("grade", filt)
    return [serialize(d) for d in docs]

@app.delete("/grades/{grade_id}")
def delete_grade(grade_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    res = db["grade"].delete_one({"_id": ObjectId(grade_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Grade not found")
    return {"deleted": True}

# Simple login to issue a token (demo only)
@app.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password required")
    token = f"token-{req.username}"
    SESSIONS.add(token)
    return LoginResponse(token=token)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
