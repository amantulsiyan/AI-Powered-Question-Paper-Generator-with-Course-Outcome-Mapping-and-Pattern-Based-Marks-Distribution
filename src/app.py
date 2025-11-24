# app.py
import os
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename

from mcq_core import (
    extract_text,
    generate_balanced_mcqs,
    save_mcqs_txt,
    save_mcqs_pdf,
)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['RESULTS_FOLDER'] = 'results/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)


# ------------------- UTIL ------------------- #

def allowed_file(filename: str) -> bool:
    return (
        '.' in filename and 
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    )


# ------------------- ROUTES ------------------- #

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate_mcqs():
    # ... (existing file and input validation code stays the same)
    
    # ---- Generate Balanced MCQs per CO ---- #
    try:
        result = generate_balanced_mcqs(text, co_list, total_questions)
        mcqs_raw = result["raw_text"]
        mapped_mcqs = result["mapped_questions"]
    except Exception as e:
        return f"Error generating MCQs: {e}"
    
    # ---- Save output files ---- #
    base_name = filename.rsplit('.', 1)[0]
    txt_name = f"generated_mcqs_{base_name}.txt"
    pdf_name = f"generated_mcqs_{base_name}.pdf"
    json_name = f"mapped_mcqs_{base_name}.json"
    
    txt_path = save_mcqs_txt(mcqs_raw, app.config['RESULTS_FOLDER'], txt_name)
    pdf_path = save_mcqs_pdf(mcqs_raw, app.config['RESULTS_FOLDER'], pdf_name)
    
    # Save CO mapping as JSON
    import json
    json_path = os.path.join(app.config['RESULTS_FOLDER'], json_name)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(mapped_mcqs, f, indent=4)
    
    # ---- Render ---- #
    return render_template(
        'result.html',
        mcqs=mcqs_raw,
        mapped_mcqs=mapped_mcqs,
        txt_filename=os.path.basename(txt_path),
        pdf_filename=os.path.basename(pdf_path),
        json_filename=json_name
    )


@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
