from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import json
from backend.utils import extract_text_from_pdf, extract_email, extract_name
from backend.llm_agents import run_resume_workflow

app = FastAPI(title="Automated Resume Triage and Shortlisting System",
                  description="A backend service for processing resumes and job descriptions.",
                  version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Automated Resume Triage and Shortlisting System API"}

@app.post("/process_resume")
async def process_resume(
    resume: UploadFile = File(...),
    meta: str = Form(None)
):
    
    try:
        file_bytes = await resume.read()
        extracted_text = extract_text_from_pdf(file_bytes)

        if not extracted_text:
            return {"error": "No text could be extracted from the resume."}
        
        email = extract_email(extracted_text)
        name = extract_name(extracted_text)

        job_data = {}
        if meta:
            try:
                job_data = json.loads(meta)
            except json.JSONDecodeError as e:
                return {"error": f"failed to parse job metadata:{e}"}

        workflow_output = run_resume_workflow(extracted_text, job_data,name,email)
        resume_summary = workflow_output["resume_summary"]
        match_result = workflow_output["match_result"]
        return {"file_name": resume.filename,
                "candidate_name":name,
                "candidate_email":email,
                "job_data": job_data,
                "resume_summary": resume_summary,
                "match_result": match_result,
                "decision_result": workflow_output.get("decision_result"),
                "email_content": workflow_output.get("email_content"),
                "text_preview": extracted_text[:1000] + "..." if len(extracted_text) > 1000 else extracted_text,
                "length": len(extracted_text)}
    
    except Exception as e:
        return {"error": f"Failed to process resume: {str(e)}"}

if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)

