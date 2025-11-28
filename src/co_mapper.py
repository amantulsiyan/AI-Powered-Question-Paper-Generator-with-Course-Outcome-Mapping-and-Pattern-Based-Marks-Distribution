from sentence_transformers import SentenceTransformer, util
import re
import json

def load_questions(filepath):
    questions = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find ALL question lines like: "Question: something"
    matches = re.findall(r"Question:\s*(.*)", content)

    for q in matches:
        # Strip numbering like "1. something" (just in case)
        clean_q = re.sub(r'^\d+\.\s*', '', q).strip()
        questions.append(clean_q)

    return questions


import re

def detect_bloom_level(question):
    q = question.lower().strip()

    # Normalize question
    q = re.sub(r'[^\w\s]', ' ', q)
    
    # Extract first few words (helps identify Bloom level)
    tokens = re.findall(r'\b[a-z]+\b', q)
    first_word = tokens[0] if tokens else ""
    first_two = " ".join(tokens[:2])

    # Extended Bloom keyword dictionary with weight scoring
    bloom_keywords = {
        "Remember": [
            "define", "list", "state", "identify", "name", "recall",
            "what", "when", "where", "label", "select", "find"
        ],
        "Understand": [
            "explain", "describe", "summarize", "interpret", "classify",
            "differentiate", "discuss", "illustrate", "why", "which of the following best",
        ],
        "Apply": [
            "apply", "use", "determine", "solve", "compute",
            "demonstrate", "execute", "implement", "calculate",
            "choose the correct", "practical", "simulate"
        ],
        "Analyze": [
            "analyze", "compare", "contrast", "differentiate",
            "distinguish", "examine", "investigate", "break down",
            "interpret data", "identify patterns"
        ],
        "Evaluate": [
            "evaluate", "justify", "critique", "argue", "assess",
            "recommend", "validate", "choose the best", "prioritize"
        ],
        "Create": [
            "create", "design", "develop", "construct", "formulate",
            "compose", "invent", "propose", "hypothesize"
        ]
    }

    # -------------- 1. FIRST VERB MATCH (most accurate) -------------- #
    for level, keywords in bloom_keywords.items():
        if first_word in keywords or first_two in keywords:
            return level

    # -------------- 2. MULTI-KEYWORD SCORING -------------- #
    scores = {level: 0 for level in bloom_keywords}

    for level, keywords in bloom_keywords.items():
        for word in keywords:
            if re.search(rf'\b{word}\b', q):
                scores[level] += 1

    # Pick the highest scoring category
    best_level = max(scores, key=scores.get)
    if scores[best_level] > 0:
        return best_level

    # -------------- 3. AI-based fallback using embeddings -------------- #
    # Only activate if all keyword matches fail
    try:
        from sentence_transformers import SentenceTransformer, util
        
        bloom_labels = [
            "Remember", "Understand", "Apply",
            "Analyze", "Evaluate", "Create"
        ]
        
        model = SentenceTransformer('all-MiniLM-L6-v2')
        q_emb = model.encode(q, convert_to_tensor=True)
        label_emb = model.encode(bloom_labels, convert_to_tensor=True)

        scores = util.cos_sim(q_emb, label_emb)[0]
        best_idx = int(scores.argmax())

        return bloom_labels[best_idx]

    except Exception:
        return "Unclassified"


def co_question_mapper(filepath):
    model=SentenceTransformer('all-MiniLM-L6-v2')
    num_cos=int(input("Enter the number of course outcomes: "))
    cos=[input(f"Enter CO{i+1} description: ")for i in range(num_cos)]
    print("\n CO descriptions recorded successfully")
    for i, co in enumerate(cos, start=1):
        print(f"CO{i}:{co}")
    print('-'*60)

    questions =load_questions(filepath)
    print("\n Questions loaded successfully")

    co_embeddings=model.encode(cos, convert_to_tensor=True)
    q_embeddings=model.encode(questions, convert_to_tensor=True)
    print("Question to CO mapping:")
    mapping_results=[]

    for i,q in enumerate(questions):
        similarities=util.cos_sim(q_embeddings[i],co_embeddings)[0]
        best_index=int(similarities.argmax())
        best_score=float(similarities[best_index])
        bloom = detect_bloom_level(q)
        result = {
            "question": q,
            "bloom_level": bloom,
            "mapped_to": f"CO{best_index+1}",
            "description": cos[best_index],
            "similarity": round(best_score, 4)
        }
        mapping_results.append(result)

        print(f"Q{i+1}: {q}")
        print(f"→ Mapped to CO{best_index+1}: {cos[best_index]}")
        print(f"   Similarity Score: {best_score:.4f}")
        print("-" * 60)
    output_file = "mapped_questions.json"
    with open(output_file, "w") as f:
        json.dump(mapping_results, f, indent=4)
    print(f"\n Mapping saved to '{output_file}'")


if __name__ == "__main__":
    path = input("Enter path to question file (.json or .txt): ")
    co_question_mapper(path)
