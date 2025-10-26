from sentence_transformers import SentenceTransformer, util
import json

def load_questions(filepath):
    '''Give filepath as the argument in the function
       Accepted formats .txt and.json '''
    if filepath.endswith('.json'):
        with open(filepath,'r')as f:
            data=json.load(f)
            questions=data.get('questions',[])
    elif filepath.endswith('.txt'):
        with open(filepath,'r')as f:
            questions=[line.strip() for line in f if line.strip()]
    else:
        raise ValueError("Unsupported file formats. Please use .json or .txt formats only")
    return questions

def detect_bloom_level(question):
    q = question.lower()
    if any(word in q for word in ["define", "list", "what is"]):
        return "Remember"
    elif any(word in q for word in ["explain", "describe", "summarize"]):
        return "Understand"
    elif any(word in q for word in ["apply", "use", "determine", "solve"]):
        return "Apply"
    elif any(word in q for word in ["analyze", "compare", "differentiate"]):
        return "Analyze"
    elif any(word in q for word in ["evaluate", "justify", "criticize"]):
        return "Evaluate"
    elif any(word in q for word in ["create", "design", "develop"]):
        return "Create"
    else:
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
