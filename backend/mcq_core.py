import os
import re
import json
import time
import requests
import docx
import pdfplumber
from fpdf import FPDF


# ===================================================================
#                      API & LLM INITIALIZATION
# ===================================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY missing! Please set it as an environment variable.")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


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
#                    CO MAPPING (keyword-based, no API)
# ===================================================================

def _keyword_similarity(text1: str, text2: str) -> float:
    words1 = set(re.findall(r'\b[a-z]+\b', text1.lower()))
    words2 = set(re.findall(r'\b[a-z]+\b', text2.lower()))
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)


# ===================================================================
#                         MCQ PARSER
# ===================================================================

def parse_and_map_mcqs(raw_text, co_list):
    mcq_blocks = raw_text.split("## MCQ")
    parsed_blocks = []

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
        parsed_blocks.append((block.strip(), question, options, correct))

    if not parsed_blocks:
        return []

    results = []
    for block, question, options, correct in parsed_blocks:
        sims = [_keyword_similarity(question, co) for co in co_list]
        best = int(max(range(len(sims)), key=lambda i: sims[i]))
        bloom = detect_bloom_level(question)
        results.append({
            "question_block": block,
            "question_text": question,
            "options": options,
            "correct_answer": correct,
            "mapped_co": f"CO{best+1}",
            "co_description": co_list[best],
            "similarity_score": round(sims[best], 4),
            "bloom_level": bloom
        })

    return results


# ===================================================================
#            MCQ GENERATION USING GROQ (plain HTTP)
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
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
        "temperature": 0.7
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    for attempt in range(retries):
        try:
            resp = requests.post(GROQ_API_URL, json=body, headers=headers, timeout=120)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(3)
    raise RuntimeError("Groq rate limit: please wait and try again with fewer questions.")


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
        if i < len(co_list) - 1:
            time.sleep(5)

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

def save_mcqs_txt(mapped_questions, folder, fname):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, fname)
    with open(path, "w", encoding="utf-8") as f:
        for i, mcq in enumerate(mapped_questions, 1):
            f.write(f"Question {i}: {mcq['question_text']}\n")
            for opt, text in mcq['options'].items():
                f.write(f"{opt}) {text}\n")
            f.write(f"Mapped CO: {mcq['mapped_co']} - {mcq['co_description']}\n")
            f.write(f"Bloom Level: {mcq['bloom_level']}\n")
            f.write("\n" + "="*60 + "\n\n")
        
        # Answers section at the end
        f.write("\n" + "="*60 + "\n")
        f.write("ANSWERS\n")
        f.write("="*60 + "\n\n")
        for i, mcq in enumerate(mapped_questions, 1):
            f.write(f"Answer_{i}: {mcq['correct_answer']}\n")
    return path


def save_mcqs_pdf(mapped_questions, folder, fname):
    os.makedirs(folder, exist_ok=True)
    pdf = FPDF()
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=9)
    
    for i, mcq in enumerate(mapped_questions, 1):
        pdf.multi_cell(0, 5, f"Question {i}: {mcq['question_text']}")
        pdf.ln(1)
        for opt, text in mcq['options'].items():
            pdf.multi_cell(0, 5, f"{opt}) {text}")
        pdf.ln(1)
        pdf.multi_cell(0, 5, f"Mapped CO: {mcq['mapped_co']} - {mcq['co_description']}")
        pdf.multi_cell(0, 5, f"Bloom Level: {mcq['bloom_level']}")
        pdf.ln(3)
    
    pdf.ln(3)
    pdf.cell(0, 5, "ANSWERS", ln=True)
    pdf.ln(1)
    for i, mcq in enumerate(mapped_questions, 1):
        pdf.cell(0, 5, f"Answer_{i}: {mcq['correct_answer']}", ln=True)
    
    path = os.path.join(folder, fname)
    pdf.output(path)
    return path
