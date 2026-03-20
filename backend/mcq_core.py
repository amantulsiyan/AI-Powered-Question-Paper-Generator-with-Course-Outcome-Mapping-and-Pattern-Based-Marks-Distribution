import os
import re
import json
import time
import requests
import docx
import pdfplumber
import numpy as np
from fpdf import FPDF


# ===================================================================
#                      API & LLM INITIALIZATION
# ===================================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY missing! Please set it as an environment variable.")

GEMINI_GENERATE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
GEMINI_EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={GEMINI_API_KEY}"


# ===================================================================
#                         TEXT EXTRACTION
# ===================================================================

def extract_text(file_path):
    ext = file_path.lower().split(".")[-1]

    if ext == "pdf":
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for p in pdf.pages:
                c = p.extract_text()
                if c:
                    text += c + "\n"
        return text

    elif ext == "docx":
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)

    elif ext == "txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    else:
        raise ValueError("Unsupported file format.")


# ===================================================================
#                    BLOOM LEVEL DETECTION
# ===================================================================

def detect_bloom_level(question):
    q = question.lower()
    tokens = re.findall(r'\b[a-z]+\b', q)
    first_word = tokens[0] if tokens else ""

    bloom_keywords = {
        "Remember":  ["define", "recall", "list", "what", "when"],
        "Understand": ["explain", "describe", "summarize", "interpret"],
        "Apply": ["apply", "use", "solve", "calculate", "determine"],
        "Analyze": ["analyze", "compare", "contrast", "distinguish"],
        "Evaluate": ["evaluate", "justify", "argue", "validate", "assess"],
        "Create": ["design", "create", "develop", "propose"]
    }

    for level, words in bloom_keywords.items():
        if first_word in words:
            return level

    for level, words in bloom_keywords.items():
        if any(w in q for w in words):
            return level

    if "why" in q or "reason" in q:
        return "Evaluate"
    if "how" in q:
        return "Analyze"

    return "Unclassified"


# ===================================================================
#                    GEMINI EMBEDDING (plain HTTP)
# ===================================================================

def _gemini_embed(texts: list) -> np.ndarray:
    embeddings = []
    for text in texts:
        body = {
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": text}]},
            "taskType": "SEMANTIC_SIMILARITY"
        }
        resp = requests.post(GEMINI_EMBED_URL, json=body, timeout=30)
        resp.raise_for_status()
        embeddings.append(resp.json()["embedding"]["values"])
    return np.array(embeddings)


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a / (np.linalg.norm(a, keepdims=True) + 1e-10)
    b = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return b @ a


# ===================================================================
#                         MCQ PARSER
# ===================================================================

def parse_and_map_mcqs(raw_text, co_list):
    co_embeddings = _gemini_embed(co_list)

    mcq_blocks = raw_text.split("## MCQ")
    results = []

    for block in mcq_blocks:
        if not block.strip():
            continue

        q_match = re.search(r"Question:\s*(.*)", block)
        if not q_match:
            continue
        question = q_match.group(1).strip()

        options = {}
        for opt in ["A", "B", "C", "D"]:
            m = re.search(rf"{opt}\)\s*(.*)", block)
            if m:
                options[opt] = m.group(1).strip()

        c_match = re.search(r"Correct Answer:\s*([A-D])", block)
        correct = c_match.group(1).upper() if c_match else "Unknown"

        q_embed = _gemini_embed([question])[0]
        sims = _cosine_sim(q_embed, co_embeddings)
        best = int(sims.argmax())

        bloom = detect_bloom_level(question)

        results.append({
            "question_block": block.strip(),
            "question_text": question,
            "options": options,
            "correct_answer": correct,
            "mapped_co": f"CO{best+1}",
            "co_description": co_list[best],
            "similarity_score": float(sims[best]),
            "bloom_level": bloom
        })

    return results


# ===================================================================
#            MCQ GENERATION USING GEMINI (plain HTTP)
# ===================================================================

def _build_co_prompt(context: str, co_description: str, num_questions: int) -> str:
    return f"""
You are an expert exam-question designer.

Generate exactly {num_questions} MCQs for the following Course Outcome (CO):

CO Description:
\"{co_description}\"

STRICT RULES:
- Use Bloom levels ONLY: Apply, Analyze, Evaluate.
- Questions must clearly reflect the CO's terminology.
- Do NOT generate purely theoretical/general questions.
- Stick to the reference text context.
- For EVERY MCQ, start with a line exactly '## MCQ'.
- Each MCQ MUST follow EXACT format:

## MCQ
Question: <question statement>
A) <option>
B) <option>
C) <option>
D) <option>
Correct Answer: <A/B/C/D>

REFERENCE TEXT:
{context}
"""


def generate_mcqs_for_co(text, co_description, n, retries=3):
    prompt = _build_co_prompt(text, co_description, n)
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2048}
    }
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.post(GEMINI_GENERATE_URL, json=body, timeout=120)
            if resp.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            last_error = e
            time.sleep(5)
    raise RuntimeError(f"Gemini generation error after {retries} attempts: {last_error}")


# ===================================================================
#    BALANCED, EXACT COUNT, RETRY-BASED GENERATION
# ===================================================================

def generate_balanced_mcqs(text, co_list, total):
    n = len(co_list)
    if n == 0:
        raise ValueError("CO list is empty.")

    base = total // n
    extra = total % n
    all_raw = ""

    for i, co in enumerate(co_list):
        count = base + (1 if i < extra else 0)
        if count <= 0:
            continue
        print(f"Generating {count} MCQs for CO{i+1}")
        out = generate_mcqs_for_co(text, co, count)
        all_raw += out + "\n\n"

    parsed = parse_and_map_mcqs(all_raw, co_list)
    print(f"First pass generated: {len(parsed)} MCQs")

    missing = total - len(parsed)
    cycles = 0
    while missing > 0 and cycles < 3:
        cycles += 1
        print(f"Retrying... Missing = {missing}")
        for co in co_list:
            if missing <= 0:
                break
            new_raw = generate_mcqs_for_co(text, co, 1)
            new_mcqs = parse_and_map_mcqs(new_raw, co_list)
            if new_mcqs:
                parsed.append(new_mcqs[0])
                missing -= 1

    parsed = parsed[:total]
    print("\nFinal MCQ Count:", len(parsed))
    return {
        "raw_text": "\n\n".join(m["question_block"] for m in parsed),
        "mapped_questions": parsed
    }


# ===================================================================
#                              SAVERS
# ===================================================================

def save_mcqs_txt(text, folder, fname):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def save_mcqs_pdf(text, folder, fname):
    os.makedirs(folder, exist_ok=True)
    pdf = FPDF()
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "NotoSans-Regular.ttf")
    pdf.add_font("Noto", "", font_path, uni=True)
    pdf.set_font("Noto", size=11)
    pdf.add_page()
    for block in text.split("## MCQ"):
        if block.strip():
            pdf.multi_cell(0, 8, block.strip())
            pdf.ln(4)
    path = os.path.join(folder, fname)
    pdf.output(path)
    return path
