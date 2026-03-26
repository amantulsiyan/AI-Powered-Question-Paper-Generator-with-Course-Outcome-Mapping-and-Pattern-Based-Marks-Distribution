import os
import re
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
        "Remember":   ["define", "recall", "list", "what", "when"],
        "Understand": ["explain", "describe", "summarize", "interpret"],
        "Apply":      ["apply", "use", "solve", "calculate", "determine"],
        "Analyze":    ["analyze", "compare", "contrast", "distinguish"],
        "Evaluate":   ["evaluate", "justify", "argue", "validate", "assess"],
        "Create":     ["design", "create", "develop", "propose"]
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
#                    CO MAPPING (keyword-based)
# ===================================================================

def _keyword_similarity(text1: str, text2: str) -> float:
    words1 = set(re.findall(r'\b[a-z]+\b', text1.lower()))
    words2 = set(re.findall(r'\b[a-z]+\b', text2.lower()))
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)


# ===================================================================
#                     MCQ PARSER  (FULLY FIXED)
# ===================================================================

def _extract_option(block: str, opt: str, next_opt) -> str:
    """
    Extract the full text of option `opt` from a raw MCQ block.
    Captures everything between 'X)' and the next option label
    or 'Correct Answer:', then collapses all internal whitespace.
    """
    if next_opt:
        stop = rf"(?=\s*{next_opt}\)\s|\s*Correct Answer:)"
    else:
        stop = rf"(?=\s*Correct Answer:)"

    pattern = rf"{opt}\)\s*(.*?){stop}"
    m = re.search(pattern, block, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    return " ".join(m.group(1).split())   # flatten any newlines


def parse_and_map_mcqs(raw_text: str, co_list: list) -> list:
    # Normalise all line-endings first
    raw_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    mcq_blocks = raw_text.split("## MCQ")
    parsed_blocks = []

    for block in mcq_blocks:
        if not block.strip():
            continue

        # ---- Question (capture up to the first option label) ----
        q_match = re.search(r"Question:\s*(.*?)(?=\n\s*A\))", block, re.DOTALL)
        if not q_match:
            continue
        question = " ".join(q_match.group(1).strip().split())

        # ---- Options (robust full-text capture) ----
        opt_labels = ["A", "B", "C", "D"]
        options = {}
        for i, opt in enumerate(opt_labels):
            next_opt = opt_labels[i + 1] if i + 1 < len(opt_labels) else None
            text = _extract_option(block, opt, next_opt)
            if text:
                options[opt] = text

        # ---- FIX 1: Skip if any option is missing ----
        if len(options) < 4:
            print(f"[SKIP] Incomplete options {list(options.keys())} in block: {question[:60]!r}")
            continue

        # ---- FIX 2: Broadened correct answer regex to handle edge cases ----
        # Handles: "Correct Answer: A", "Correct Answer: (A)", "Correct Answer: A)"
        # "Correct Answer: A or B", "Correct answer: a", etc.
        c_match = re.search(
            r"Correct Answer[:\s]*\(?([A-D])\)?",
            block,
            re.IGNORECASE
        )
        correct = c_match.group(1).upper() if c_match else "Unknown"

        # ---- FIX 3: Skip if correct answer could not be determined ----
        if correct == "Unknown":
            print(f"[SKIP] Could not parse correct answer in block: {question[:60]!r}")
            continue

        parsed_blocks.append((block.strip(), question, options, correct))

    if not parsed_blocks:
        return []

    results = []
    for block, question, options, correct in parsed_blocks:
        sims = [_keyword_similarity(question, co) for co in co_list]
        best = int(max(range(len(sims)), key=lambda i: sims[i]))
        bloom = detect_bloom_level(question)
        results.append({
            "question_block":   block,
            "question_text":    question,
            "options":          options,
            "correct_answer":   correct,
            "mapped_co":        f"CO{best + 1}",
            "co_description":   co_list[best],
            "similarity_score": round(sims[best], 4),
            "bloom_level":      bloom,
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

- DO NOT refer to "given code", "above code", or "following code" unless code is explicitly present in the reference text.
- Questions must be fully self-contained and understandable independently.

- Start every MCQ with exactly '## MCQ' on its own line.
- EVERY MCQ MUST have EXACTLY 4 options: A, B, C, and D. Never skip any option.
- CRITICAL: EACH OPTION (A, B, C, D) MUST FIT ON A SINGLE LINE.
  Do NOT insert any line break or newline inside an option's text.
- Correct Answer must be exactly one letter: A, B, C, or D. Nothing else.
- Follow EXACTLY this format and nothing else:

## MCQ
Question: <question statement on one line>
A) <full option text on one single line, no newlines>
B) <full option text on one single line, no newlines>
C) <full option text on one single line, no newlines>
D) <full option text on one single line, no newlines>
Correct Answer: <A or B or C or D>

REFERENCE TEXT:
{context}
"""


def generate_mcqs_for_co(text, co_description, n, retries=3):
    prompt = _build_co_prompt(text, co_description, n)
    body = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
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
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(3)
    raise RuntimeError("Groq rate limit: please wait and try again with fewer questions.")


# ===================================================================
#    BALANCED, EXACT COUNT, RETRY-BASED GENERATION
# ===================================================================

def generate_balanced_mcqs(text, co_list, total):
    n = len(co_list)
    if n == 0:
        raise ValueError("CO list is empty.")

    base  = total // n
    extra = total % n
    all_raw = ""

    for i, co in enumerate(co_list):
        # FIX 4: Add 20% buffer per CO to compensate for skipped malformed MCQs
        base_count = base + (1 if i < extra else 0)
        count = max(1, round(base_count * 1.2))

        print(f"Generating {count} MCQs for CO{i + 1} (target: {base_count}, +20% buffer)")
        out = generate_mcqs_for_co(text, co, count)
        all_raw += out + "\n\n"
        if i < len(co_list) - 1:
            time.sleep(5)

    parsed = parse_and_map_mcqs(all_raw, co_list)
    print(f"First pass generated: {len(parsed)} valid MCQs")

    # Retry loop to fill any remaining gap
    missing = total - len(parsed)
    cycles  = 0
    while missing > 0 and cycles < 3:
        cycles += 1
        print(f"Retrying... Missing = {missing}")
        for co in co_list:
            if missing <= 0:
                break
            new_raw  = generate_mcqs_for_co(text, co, 1)
            new_mcqs = parse_and_map_mcqs(new_raw, co_list)
            if new_mcqs:
                parsed.append(new_mcqs[0])
                missing -= 1

    parsed = parsed[:total]
    print(f"\nFinal MCQ Count: {len(parsed)}")
    return {
        "raw_text":         "\n\n".join(m["question_block"] for m in parsed),
        "mapped_questions": parsed,
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
            for opt in ["A", "B", "C", "D"]:
                opt_text = mcq["options"].get(opt, "")
                if opt_text:
                    f.write(f"{opt}) {opt_text}\n")
            f.write(f"Mapped CO: {mcq['mapped_co']} - {mcq['co_description']}\n")
            f.write(f"Bloom Level: {mcq['bloom_level']}\n")
            f.write("\n" + "=" * 60 + "\n\n")

        f.write("\n" + "=" * 60 + "\n")
        f.write("ANSWERS\n")
        f.write("=" * 60 + "\n\n")
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
    w = pdf.epw   # effective page width (accounts for both margins)

    for i, mcq in enumerate(mapped_questions, 1):

        # ---- Question number + text ----
        pdf.set_font("Helvetica", style="B", size=9)
        pdf.multi_cell(w, 5, f"Q{i}.", ln=True)
        pdf.set_font("Helvetica", size=9)
        pdf.multi_cell(w, 5, mcq["question_text"], ln=True)
        pdf.ln(1)

        # ---- Options (each value is already a flat single-line string) ----
        for opt in ["A", "B", "C", "D"]:
            opt_text = mcq["options"].get(opt, "")
            if opt_text:
                pdf.cell(5)
                pdf.multi_cell(w - 5, 5, f"{opt}) {opt_text}", ln=True)

        pdf.ln(1)

        # ---- Metadata ----
        pdf.set_font("Helvetica", style="I", size=8)
        pdf.multi_cell(w, 4, f"Mapped CO: {mcq['mapped_co']} - {mcq['co_description']}", ln=True)
        pdf.multi_cell(w, 4, f"Bloom Level: {mcq['bloom_level']}", ln=True)
        pdf.set_font("Helvetica", size=9)
        pdf.ln(5)

    # ---- Answer key on a new page ----
    pdf.add_page()
    pdf.set_font("Helvetica", style="B", size=10)
    pdf.cell(w, 7, "ANSWER KEY", ln=True)
    pdf.set_font("Helvetica", size=9)
    pdf.ln(2)
    for i, mcq in enumerate(mapped_questions, 1):
        pdf.cell(w, 5, f"Answer_{i}: {mcq['correct_answer']}", ln=True)

    path = os.path.join(folder, fname)
    pdf.output(path)
    return path

def save_mcqs_docx(mapped_questions, folder, fname):
    os.makedirs(folder, exist_ok=True)
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Title
    title = doc.add_heading("AI-Generated MCQs", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for i, mcq in enumerate(mapped_questions, 1):
        # Question
        q_para = doc.add_paragraph()
        q_run = q_para.add_run(f"Q{i}. {mcq['question_text']}")
        q_run.bold = True
        q_run.font.size = Pt(11)

        # Options
        for opt in ["A", "B", "C", "D"]:
            opt_text = mcq["options"].get(opt, "")
            if opt_text:
                doc.add_paragraph(f"{opt}) {opt_text}", style="List Bullet")

        # Metadata
        meta = doc.add_paragraph()
        meta_run = meta.add_run(
            f"Mapped CO: {mcq['mapped_co']} - {mcq['co_description']} | Bloom Level: {mcq['bloom_level']}"
        )
        meta_run.italic = True
        meta_run.font.size = Pt(9)
        meta_run.font.color.rgb = RGBColor(0x88, 0x88, 0x99)

        doc.add_paragraph("─" * 60)

    # Answer key
    doc.add_page_break()
    doc.add_heading("Answer Key", 1)
    for i, mcq in enumerate(mapped_questions, 1):
        doc.add_paragraph(f"Answer_{i}: {mcq['correct_answer']}")

    path = os.path.join(folder, fname)
    doc.save(path)
    return path