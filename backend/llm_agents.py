import os
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from langgraph.graph import StateGraph
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def _call_gemini(prompt: str, model_name: str = "gemini-2.5-flash") -> str:
    model = genai.GenerativeModel(model_name)
    resp = model.generate_content(prompt)
    text = getattr(resp, "text", None)
    if not text and getattr(resp, "candidates", None):
        try:
            parts = resp.candidates[0].content.parts
            text = "".join([getattr(p, "text", "") for p in parts])
        except Exception:
            text = str(resp)
    return (text or "").strip()

def summarize_resume(state):
    resume_text = state.get("resume_text", "") or ""
    prompt = f"""
You are a professional technical recruiter.
Summarize this resume into strict JSON with exactly these fields:
{{ "summary": "80-100 word professional summary", "skills": ["skill1", "skill2"], "experience_years": <integer>, "education": "Highest qualification" }}
Output ONLY valid JSON. No markdown, no explanations.
Resume:
{resume_text}
"""
    text = _call_gemini(prompt, model_name="gemini-2.5-flash")
    try:
        parsed = json.loads(text)
    except Exception:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        parsed = json.loads(m.group(0)) if m else {"summary": "Parsing failed", "skills": [], "experience_years": 0, "education": ""}
    state["resume_summary"] = parsed
    return state

def match_resume_to_job(state):
    resume_summary = state.get("resume_summary", {})
    job_data = state.get("job_data", {}) or {}
    title = job_data.get("title", "")
    desc = job_data.get("description", "")
    skills = job_data.get("must_have_skills", "")
    prompt = f"""
You are an AI recruiter evaluating a candidate.
Rate the candidate from 0 to 100 and provide a 2-line reasoning in JSON.
Job Title: {title}
Description: {desc}
Must-have Skills: {skills}
Candidate Summary: {json.dumps(resume_summary)}
Output only JSON: {{ "score": <integer>, "reasoning": "<2-line explanation>" }}
"""
    text = _call_gemini(prompt, model_name="gemini-2.5-flash")
    try:
        parsed = json.loads(text)
    except Exception:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        parsed = json.loads(m.group(0)) if m else {"score": 0, "reasoning": "Parsing failed"}
    state["match_result"] = parsed
    return state

def decide_candidate(state):
    match_result = state.get("match_result", {})
    if isinstance(match_result, str):
        try:
            match_result = json.loads(match_result)
        except Exception:
            match_result = {"score": 0, "reasoning": "Invalid data"}
    score = match_result.get("score", 0)
    reasoning = match_result.get("reasoning", "")
    threshold = 70
    decision = "Accepted" if score >= threshold else "Rejected"
    if score >= threshold:
        feedback = "Strong match — consider inviting the candidate for an interview."
    else:
        feedback = "Profile does not fully meet role requirements. Candidate may need more experience or key skills."
    state["decision_result"] = {"decision": decision, "threshold": threshold, "score": score, "feedback": feedback, "reasoning": reasoning}
    return state

def send_real_email(to_email, subject, message):
    host = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    port = int(os.getenv("EMAIL_PORT", "587"))
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")

    if not all([to_email, user, password]):
        raise RuntimeError("Missing email credentials or recipient")

    try:
        msg = MIMEMultipart()
        msg["From"] = user
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

        return "✅ Email sent successfully"
    except smtplib.SMTPAuthenticationError:
        return "❌ Authentication failed — check Gmail App Password"
    except Exception as e:
        return f"❌ Failed to send email: {str(e)}"


def send_email(state):
    candidate_email = state.get("candidate_email", "")
    candidate_name = state.get("candidate_name", "Candidate")
    decision_data = state.get("decision_result", {})

    if isinstance(decision_data, str):
        try:
            decision_data = json.loads(decision_data)
        except Exception:
            decision_data = {"decision": "Rejected", "feedback": "Error parsing decision", "score": 0}

    decision = decision_data.get("decision", "Rejected")
    feedback = decision_data.get("feedback", "")
    score = decision_data.get("score", 0)

    subject = f"Application Update — Your Result: {decision}"

    if decision == "Accepted":
        message_body = f"""
Dear {candidate_name},

Congratulations! 🎉
Your profile has been shortlisted successfully.

Score: {score}/100
Feedback: {feedback}

Our HR team will contact you soon.

Regards,
HR Team
"""
    else:
        message_body = f"""
Dear {candidate_name},

Thank you for applying.
Unfortunately, your profile was not shortlisted this time.

Score: {score}/100
Feedback: {feedback}

We encourage you to apply again in the future.

Regards,
HR Team
"""

    send_status = "⚠️ Email sending disabled"
    if os.getenv("EMAIL_SEND", "false").lower() == "true":
        send_status = send_real_email(candidate_email, subject, message_body)

    state["email_content"] = {
        "to": candidate_email,
        "subject": subject,
        "body": message_body.strip(),
        "send_status": send_status,
    }

    print(f"[EMAIL DEBUG] → {send_status}")  # visible in Render logs

    return state


workflow = StateGraph(dict)
workflow.add_node("summarize_resume", summarize_resume)
workflow.add_node("match_resume_to_job", match_resume_to_job)
workflow.add_node("decide_candidate", decide_candidate)
workflow.add_node("send_email", send_email)
workflow.add_edge("summarize_resume", "match_resume_to_job")
workflow.add_edge("match_resume_to_job", "decide_candidate")
workflow.add_edge("decide_candidate", "send_email")
workflow.set_entry_point("summarize_resume")
workflow.set_finish_point("send_email")
graph = workflow.compile()

def run_resume_workflow(resume_text: str, job_data: dict, candidate_name: str = "", candidate_email: str = ""):
    result = graph.invoke({"resume_text": resume_text, "job_data": job_data, "candidate_name": candidate_name, "candidate_email": candidate_email})
    for key in ["resume_summary", "match_result", "decision_result", "email_content"]:
        if isinstance(result.get(key), str):
            try:
                result[key] = json.loads(result[key])
            except Exception:
                pass
    return result

