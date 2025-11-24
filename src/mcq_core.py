import os
import re
import docx
import pdfplumber
from fpdf import FPDF
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from sentence_transformers import SentenceTransformer, util

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

Generate {num_questions} HIGH-QUALITY MCQs that explicitly assess the following Course Outcome (CO):

CO Description:
"{co_description}"

Your MCQs MUST:
- clearly reflect concepts and terminology mentioned in the CO
- include keywords and phrasing inspired directly from the CO language
- stay strictly within the scope of the CO (do NOT generate generic or broad questions)
- use Bloom levels: Apply, Analyze, or Evaluate
- use the reference text ONLY as supporting material

To ensure proper CO alignment:
- each question MUST contain at least some terminology related to the CO description
- avoid generic questions unless relevant to the CO text
- focus on the specific learning objectives stated in the CO

Reference Text:
{context}

Format each MCQ EXACTLY like this:

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
    """Extract text from PDF, DOCX, or TXT files"""
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

# ---------- BLOOM LEVEL DETECTION ---------- #

def detect_bloom_level(question):
    """Detect Bloom's taxonomy level based on question verbs"""
    q = question.lower()
    tokens = re.findall(r'\b[a-z]+\b', q)
    first_word = tokens[0] if tokens else ""
    
    bloom_keywords = {
        "Remember": [
            "define", "list", "state", "identify", "name", "recall",
            "what", "when", "where", "who", "label", "match", "memorize"
        ],
        "Understand": [
            "explain", "describe", "summarize", "interpret", "classify",
            "differentiate", "discuss", "illustrate", "paraphrase", "translate"
        ],
        "Apply": [
            "apply", "use", "determine", "solve", "compute",
            "demonstrate", "execute", "implement", "calculate", "show"
        ],
        "Analyze": [
            "analyze", "compare", "contrast", "differentiate",
            "distinguish", "examine", "investigate", "categorize", "break down"
        ],
        "Evaluate": [
            "evaluate", "justify", "critique", "argue", "assess",
            "recommend", "validate", "judge", "defend", "support"
        ],
        "Create": [
            "create", "design", "develop", "construct", "formulate",
            "compose", "invent", "propose", "plan", "generate"
        ]
    }
    
    # Check first word (most reliable indicator)
    for level, keywords in bloom_keywords.items():
        if first_word in keywords:
            return level
    
    # Fallback: check anywhere in the question
    for level, keywords in bloom_keywords.items():
        if any(re.search(rf'\b{word}\b', q) for word in keywords):
            return level
    
    return "Unclassified"

# ---------- CO MAPPING ---------- #

def parse_and_map_mcqs(raw_mcqs, co_list):
    """
    Parse generated MCQs and map them to COs using semantic similarity.
    Returns a list of dictionaries containing question details and CO mappings.
    """
    # Initialize sentence transformer model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    co_embeddings = model.encode(co_list, convert_to_tensor=True)
    
    # Parse MCQs from raw text
    mcq_blocks = raw_mcqs.split("## MCQ")
    mapped_mcqs = []
    
    for block in mcq_blocks:
        if not block.strip():
            continue
            
        # Extract question text
        question_match = re.search(r"Question:\s*(.*?)(?:\n|$)", block, re.IGNORECASE)
        if not question_match:
            continue
            
        question_text = question_match.group(1).strip()
        
        # Skip if question is too short
        if len(question_text) < 10:
            continue
        
        # Encode question and find best CO match using semantic similarity
        q_embedding = model.encode(question_text, convert_to_tensor=True)
        similarities = util.cos_sim(q_embedding, co_embeddings)[0]
        best_index = int(similarities.argmax())
        best_score = float(similarities[best_index])
        
        # Detect Bloom level
        bloom = detect_bloom_level(question_text)
        
        # Extract options and correct answer
        options = {}
        for opt in ['A', 'B', 'C', 'D']:
            opt_match = re.search(rf"{opt}\)\s*(.*?)(?:\n|$)", block)
            if opt_match:
                options[opt] = opt_match.group(1).strip()
        
        correct_match = re.search(r"Correct Answer:\s*([A-D])", block, re.IGNORECASE)
        correct_answer = correct_match.group(1).upper() if correct_match else "Unknown"
        
        mapped_mcqs.append({
            "question_block": block.strip(),
            "question_text": question_text,
            "options": options,
            "correct_answer": correct_answer,
            "mapped_co": f"CO{best_index + 1}",
            "co_description": co_list[best_index],
            "similarity_score": round(best_score, 4),
            "bloom_level": bloom
        })
    
    return mapped_mcqs

# ---------- CO-AWARE MCQ GENERATION ---------- #

def generate_mcqs_for_co(text, co_description, num_questions):
    """Generate MCQs for a specific Course Outcome"""
    response = co_chain.invoke({
        "context": text,
        "co_description": co_description,
        "num_questions": num_questions
    })

    return response.content.strip() if hasattr(response, "content") else str(response)

def generate_balanced_mcqs(text, co_list, total_questions):
    """
    Generate MCQs balanced across all COs and map them using semantic similarity.
    Returns a dictionary with raw text and mapped questions.
    """
    per_co = total_questions // len(co_list)
    
    all_mcqs_raw = ""
    
    # Generate MCQs for each CO
    for i, co in enumerate(co_list):
        print(f"Generating {per_co} MCQs for CO{i+1}...")
        mcqs = generate_mcqs_for_co(text, co, per_co)
        all_mcqs_raw += mcqs + "\n\n"
    
    # Parse and map MCQs to COs using semantic similarity
    print("Mapping MCQs to COs using semantic similarity...")
    mapped_mcqs = parse_and_map_mcqs(all_mcqs_raw, co_list)
    
    return {
        "raw_text": all_mcqs_raw.strip(),
        "mapped_questions": mapped_mcqs
    }

# ---------- SAVE HELPERS ---------- #

def save_mcqs_txt(mcqs, folder, filename):
    """Save MCQs to a text file"""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(mcqs)
    return path

def save_mcqs_pdf(mcqs, folder, filename):
    """Save MCQs to a PDF file"""
    os.makedirs(folder, exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for mcq in mcqs.split("## MCQ"):
        if mcq.strip():
            # Handle special characters that might cause issues
            try:
                pdf.multi_cell(0, 10, mcq.strip())
                pdf.ln(5)
            except Exception as e:
                # Fallback for encoding issues
                clean_text = mcq.strip().encode('latin-1', 'ignore').decode('latin-1')
                pdf.multi_cell(0, 10, clean_text)
                pdf.ln(5)

    path = os.path.join(folder, filename)
    pdf.output(path)
    return path

def save_mapped_mcqs_json(mapped_mcqs, folder, filename):
    """Save CO-mapped MCQs to a JSON file"""
    import json
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(mapped_mcqs, f, indent=4, ensure_ascii=False)
    return path

def save_mapped_mcqs_txt(mapped_mcqs, folder, filename):
    """Save CO-mapped MCQs to a detailed text file"""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("CO-MAPPED MCQs WITH BLOOM LEVELS\n")
        f.write("="*80 + "\n\n")
        
        for i, mcq in enumerate(mapped_mcqs, 1):
            f.write(f"Question {i}:\n")
            f.write(f"{mcq['question_text']}\n\n")
            
            for opt, text in mcq['options'].items():
                f.write(f"{opt}) {text}\n")
            
            f.write(f"\nCorrect Answer: {mcq['correct_answer']}\n")
            f.write(f"Mapped to: {mcq['mapped_co']}\n")
            f.write(f"CO Description: {mcq['co_description']}\n")
            f.write(f"Similarity Score: {mcq['similarity_score']}\n")
            f.write(f"Bloom Level: {mcq['bloom_level']}\n")
            f.write("-"*80 + "\n\n")
    
    return path