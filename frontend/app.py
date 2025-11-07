import streamlit as st
import requests
import json

fastapi_url = "https://automated-resume-triage-and-shortlisting.onrender.com/"

st.set_page_config(page_title="Automated Resume Triage", layout="wide")
st.title("Automated Resume Triage and Shortlisting")

st.sidebar.header("User Type")
user_type = st.sidebar.radio("Select:",["Recruiter", "Candidate"])

if user_type == "Recruiter":
    st.subheader("Recruiter Section")
    st.write("Upload a job description and view shortlisted resumes here.")

    job_title = st.text_input("Enter Job Title")
    job_description = st.text_area("Enter Job Description")
    must_have_skills = st.text_input("Enter Must-Have Skills (comma separated)")
    
    if st.button("Save Job Details"):
        if not job_title or not job_description:
            st.error("Please fill in all the job details.") 
        else:
            st.session_state["job"] = {
                "title": job_title,
                "description": job_description,
                "must_have_skills": must_have_skills
            }
            st.success("Job details saved successfully!")

else:
    st.subheader("Candidate Section - Upload Your Resume")

    uploaded_file = st.file_uploader("Choose your resume (PDF, DOCX format only)", type=["pdf", "docx"])

    if "job" not in st.session_state:
        st.warning("Please ask a recruiter to enter job details first.")
    else:
        if uploaded_file is not None:
            if st.button("Submit Resume"):
                with st.spinner("Uploading and extracting text..."):
                    files = {"resume": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    meta = json.dumps({"job": st.session_state["job"]})
                    try:
                        response = requests.post(fastapi_url, files=files, data={"meta": meta})
                        if response.status_code == 200:
                            data = response.json()
                            if "error" in data:
                                st.error(data["error"])
                            else:
                                st.success(f"{data['file_name']} processed successfully!")
                                st.write(f"**Candidate Name:** {data.get('candidate_name')}")
                                st.write(f"**Candidate Email:** {data.get('candidate_email')}")
                                st.write(f"**Extracted Text Length:** {data['length']} characters")
                                st.text_area("Extracted Text Preview", data["text_preview"], height=300)

                                if "resume_summary" in data:
                                    st.markdown("### Resume Summary")
                                    st.json(data["resume_summary"])

                                if "match_result" in data:
                                    st.markdown("### Match Evaluation")
                                    st.write(f"**Score:** {data['match_result'].get('score')}/100")
                                    st.write(f"**Reasoning:** {data['match_result'].get('reasoning')}")
                        else:
                            st.error(f"Backend returned status code {response.status_code}")
                    except Exception as e:

                        st.error(f"Request failed: {e}")
