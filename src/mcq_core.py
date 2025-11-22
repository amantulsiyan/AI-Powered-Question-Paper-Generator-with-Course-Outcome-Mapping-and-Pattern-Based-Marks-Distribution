import os
import docx
import pdfplumber
from fpdf import FPDF
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq

# ---------------- CONFIG ---------------- #

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set. Please export it first.")

llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.3-70b-versatile",
    temperature=0.2
)

# -------------- PROMPTS ---------------- #

co_controlled_prompt = PromptTemplate(
    input_variables=["context", "co_description", "num_questions"],
    template="""
You are an expert exam-question designer.

Generate {num_questions} HIGH-QUALITY MCQs strictly aligned to the following CO:

CO Description:
"{co_description}"

The questions MUST:
- Test ONLY this CO
- Be unique and non-repetitive
- Cover real exam concepts
- Use Bloom levels: Apply, Analyze, or Evaluate
- Use the text below ONLY as reference material

Reference Text:
{context}

Format each question as:

## MCQ
Question: <question>
A) <option 1>
B) <option 2>
C) <option 3>
D) <option 4>
Correct Answer: <correct option letter>
"""
)

co_chain = co_controlled_prompt | llm

# ------------ TEXT EXTRACTION ------------ #

def extract_text(file_path):
    ext = file_path.lower().split(".")[-1]

    if ext == "pdf":
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                content = page.extract_text()
                if content:
                    text += content + "\n"
        return text

    elif ext == "docx":
        doc = docx.Document(file_path)
        return "\n".join(para.text for para in doc.paragraphs)

    elif ext == "txt":
        return open(file_path, "r", encoding="utf-8").read()

    else:
        raise ValueError(f"Unsupported file type: {ext}")

# ---------- CO-AWARE MCQ GENERATION ---------- #

def generate_mcqs_for_co(text, co_description, num_questions):
    response = co_chain.invoke({
        "context": text,
        "co_description": co_description,
        "num_questions": num_questions
    })

    return response.content.strip() if hasattr(response, "content") else str(response)

def generate_balanced_mcqs(text, co_list, total_questions):
    per_co = total_questions // len(co_list)

    all_mcqs = ""

    for co in co_list:
        mcqs = generate_mcqs_for_co(text, co, per_co)
        all_mcqs += mcqs + "\n\n"

    return all_mcqs.strip()

# ---------- SAVE HELPERS ---------- #

def save_mcqs_txt(mcqs, folder, filename):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(mcqs)
    return path

def save_mcqs_pdf(mcqs, folder, filename):
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
