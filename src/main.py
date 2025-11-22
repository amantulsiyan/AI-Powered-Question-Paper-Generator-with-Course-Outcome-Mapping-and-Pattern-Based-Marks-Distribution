# main.py
import os
from mcq_core import (
    extract_text,
    generate_balanced_mcqs,
    save_mcqs_txt,
    save_mcqs_pdf,
)

# --------------- CONFIG ---------------- #

UPLOAD_FILE = "The Wonders of Science.docx"   # change this to your test file
TOTAL_QUESTIONS = 10                          # total MCQs required
RESULTS_FOLDER = "results"

# ---------------------------------------- #

def main():

    # ---------------- FILE CHECK ---------------- #
    if not os.path.exists(UPLOAD_FILE):
        print(f"❌ File not found: {UPLOAD_FILE}")
        return

    # ---------------- INPUT COs ---------------- #
    print("Enter COs (one per line).")
    print("Type 'done' when finished.\n")

    co_list = []
    while True:
        co = input("CO: ").strip()
        if co.lower() == "done":
            break
        if co:
            co_list.append(co)

    if len(co_list) == 0:
        print("❌ No COs provided. Exiting.")
        return

    # ---------------- PROCESSING ---------------- #
    print("\n📘 Extracting text...")
    text = extract_text(UPLOAD_FILE)

    print("🧠 Generating balanced MCQs across all COs...")
    mcqs = generate_balanced_mcqs(text, co_list, TOTAL_QUESTIONS)

    # ---------------- SAVING ---------------- #
    base_name = os.path.basename(UPLOAD_FILE).rsplit('.', 1)[0]
    txt_name = f"generated_mcqs_{base_name}.txt"
    pdf_name = f"generated_mcqs_{base_name}.pdf"

    txt_path = save_mcqs_txt(mcqs, RESULTS_FOLDER, txt_name)
    pdf_path = save_mcqs_pdf(mcqs, RESULTS_FOLDER, pdf_name)

    print("\n✅ MCQ Generation Complete!")
    print(f"📄 MCQs saved to:\n- {txt_path}\n- {pdf_path}")

if __name__ == "__main__":
    main()
