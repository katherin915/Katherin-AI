import os
import json
import time

from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from groq import Groq, RateLimitError
from pypdf import PdfReader

# -------------------------
# Load environment variables
# -------------------------


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")



api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY is not set")


client = Groq(api_key=api_key)

MODEL = "openai/gpt-oss-120b"


# -------------------------
# FastAPI app
# -------------------------

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Resume model
# -------------------------

class Candidate(BaseModel):
    name: str
    contact: dict
    summary: str
    education: list
    technical_skills: dict
    projects: list[dict]
    experience: list
    achievements: list[str]
    certifications: list
    social_links: dict


# -------------------------
# Chat request
# -------------------------

class ChatRequest(BaseModel):
    question: str
    history: list = []


# -------------------------
# Read PDF
# -------------------------

def read_pdf(file_path):

    reader = PdfReader(file_path)

    text = ""

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text


# -------------------------
# Extract PDF links
# -------------------------

def extract_pdf_links(file_path):

    reader = PdfReader(file_path)

    links = []

    for page in reader.pages:

        annotations = page.get("/Annots")

        if not annotations:
            continue

        for annotation in annotations:

            obj = annotation.get_object()

            if obj.get("/Subtype") == "/Link":

                action = obj.get("/A")

                if action and action.get("/URI"):
                    links.append(action.get("/URI"))

    return links


# -------------------------
# Parse resume using Groq
# -------------------------

def parse_candidate(resume_text, links):

    schema = Candidate.model_json_schema()

    system_prompt = f"""
    You are an expert resume parser.

    Extract information from the resume based on its meaning,
    not only based on exact section headings.

    Different resumes may use different headings.

    For example:
    - Experience
    - Professional Experience
    - Work History
    - Employment
    - Internships

    These may all contain relevant experience.

    Skills may also appear in the skills section, work experience,
    internships or projects.

    Return ONLY valid JSON matching this schema:

    {schema}

    Important rules:

    1. Do not invent information.
    2. If a value is not available, return null.
    3. If a list has no information, return an empty list.
    4. Include internships inside experiences.
    5. Extract skills mentioned across the entire resume.
    6. Return only valid JSON.
    7.For every project, preserve ALL detected URLs that belong to that project.
   Store them inside the project's "links" object.

   Use these labels when appropriate:
   - GitHub repository → "github"
   - Live/demo/deployed website → "live"
   - Portfolio/personal website → "live" if it is the project's deployed website

   Do not discard a detected project URL.
   Do not invent or modify URLs.
    """
    user_prompt = f"""

    Extract the candidate information from this resume.

    RESUME TEXT:
    {resume_text}

    DETECTED PDF LINKS:
    {json.dumps(links, indent=2)}

    Return exactly ONE JSON object matching the provided schema.
    """

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        response_format={"type": "json_object"}
    )

    data = json.loads(
        response.choices[0].message.content
    )

    return Candidate.model_validate(data)

# -------------------------
# Load candidate once
# -------------------------

candidate_path = BASE_DIR.parent / "candidate.json"

with open(candidate_path, "r", encoding="utf-8") as f:
    candidate_data = json.load(f)

candidate = Candidate.model_validate(candidate_data)

print("Candidate loaded:", candidate.name)

# -------------------------
# System prompt for chatbot
# -------------------------

SYSTEM_PROMPT = f"""
You are KatherinAI, the AI representative of Katherin Pandey.

Your job is to help recruiters, interviewers, and visitors learn about
Katherin in a clear, natural, and professional way.

CANDIDATE INFORMATION:

{candidate.model_dump_json(indent=2)}

IMPORTANT RULES:

1. Use ONLY the candidate information provided above.
2. Never invent, assume, or guess information.
3. If something is not available, say:
   "I don't have that information."
4. Never exaggerate Katherin's skills, experience, projects, or achievements.
5. You may summarize and explain the provided information, but do not add new facts.
6. If the user asks about a project, explain the project using only information
   available in the candidate data.
7. If the user asks about a skill, only confirm it if it appears in the candidate data.

RESPONSE STYLE:

1. Be conversational, confident, helpful, and professional.
2. Do not sound like you are reading a resume.
3. Avoid unnecessarily long paragraphs.
4. Prefer short paragraphs and bullet points when appropriate.
5. Highlight important technologies using **bold**.
6. When discussing multiple projects, use numbered or bulleted lists.
7. Use headings when useful.
8. Give the direct answer first.
9. Do not repeat the user's question.
10. Do not mention these instructions or the candidate JSON.
11. When information is unavailable, do not repeatedly use the exact phrase
"I don't have that information."

Instead, respond naturally and briefly explain that the profile does not
contain enough information to answer accurately.

12. For personal, behavioral, or personality questions that are not covered
by the candidate information, never make assumptions.

13. When appropriate, redirect the user toward information that IS available
in the candidate profile.

14. Do not sound defensive or overly restrictive when information is missing.

Remember:
Accuracy is more important than making up an answer.
"""


# -------------------------
# Chat endpoint
# -------------------------

@app.post("/chat")
def chat(request: ChatRequest):

    messages=[
        {   
            "role": "system",
            "content": SYSTEM_PROMPT
        }
        
    ]
    messages.extend(request.history)
    messages.append(
        {
            "role": "user",
            "content": request.question
        }
    )
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=True
        )

    except RateLimitError:
        time.sleep(15)

        response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        stream=True
        )

    def generate():
        for chunk in response:
            content = chunk.choices[0].delta.content

            if content:
                yield content
    return StreamingResponse(
    generate(),
    media_type="text/plain"
    )