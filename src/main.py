# main.py
import os
from mcq_core import generate_mcqs_from_file, save_mcqs_txt, save_mcqs_pdf

UPLOAD_FILE = "The Wonders of Science.docx"  # or any file path
NUM_QUESTIONS = 5
RESULTS_FOLDER = "results"

def main():
    if not os.path.exists(UPLOAD_FILE):
        print(f"File not found: {UPLOAD_FILE}")
        return

    print(f"Generating MCQs from: {UPLOAD_FILE}")
    try:
        mcqs = generate_mcqs_from_file(UPLOAD_FILE, NUM_QUESTIONS)
    except Exception as e:
        print(f"Error: {e}")
        return

    base_name = os.path.basename(UPLOAD_FILE).rsplit('.', 1)[0]
    txt_name = f"generated_mcqs_{base_name}.txt"
    pdf_name = f"generated_mcqs_{base_name}.pdf"

    txt_path = save_mcqs_txt(mcqs, RESULTS_FOLDER, txt_name)
    pdf_path = save_mcqs_pdf(mcqs, RESULTS_FOLDER, pdf_name)

    print(f"MCQs saved to:\n- {txt_path}\n- {pdf_path}")

if __name__ == "__main__":
    main()
