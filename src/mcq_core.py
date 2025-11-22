# mcq_core.py
import os
import pdfplumber
import docx
from fpdf import FPDF

from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq

# ------------ LLM SETUP ------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY environment variable is not set. "
        "Set it before running the app or main script."
    )

llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.3-70b-versatile",
    temperature=0.0,
)

mcq_prompt = PromptTemplate(
    input_variables=["context", "num_questions"],
    template="""
You are an AI assistant helping the user generate multiple-choice questions (MCQs) from the text below:

Text:
{context}

Generate {num_questions} MCQs. Each should include:
- A clear question
- Four answer options labeled A, B, C, and D
- The correct answer clearly indicated at the end

Format:
## MCQ
Question: [question]
A) [option A]
B) [option B]
C) [option C]
D) [option D]
Correct Answer: [correct option]
"""
)

mcq_chain = mcq_prompt | llm  # LCEL chain

# ------------ TEXT EXTRACTION ------------

def extract_text(file_path: str) -> str:
    ext = file_path.rsplit('.', 1)[-1].lower()

    if ext == "pdf":
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text

    elif ext == "docx":
        doc = docx.Document(file_path)
        return " ".join(para.text for para in doc.paragraphs)

    elif ext == "txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    else:
        raise ValueError(f"Unsupported file type: {ext}")

# ------------ MCQ GENERATION ------------

def generate_mcqs_from_text(text: str, num_questions: int) -> str:
    response = mcq_chain.invoke({
        "context": text,
        "num_questions": num_questions,
    })

    if hasattr(response, "content"):
        return response.content.strip()
    return str(response).strip()

def generate_mcqs_from_file(file_path: str, num_questions: int) -> str:
    text = extract_text(file_path)
    if not text or not text.strip():
        raise ValueError("No text extracted from the file.")
    return generate_mcqs_from_text(text, num_questions)

# ------------ SAVE HELPERS ------------

def save_mcqs_txt(mcqs: str, folder: str, filename: str) -> str:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(mcqs)
    return path

def save_mcqs_pdf(mcqs: str, folder: str, filename: str) -> str:
    os.makedirs(folder, exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for mcq in mcqs.split("## MCQ"):
        if mcq.strip():
            pdf.multi_cell(0, 10, mcq.strip())
            pdf.ln(5)

    path = os.path.join(folder, filename)
    pdf.output(path)
    return path
