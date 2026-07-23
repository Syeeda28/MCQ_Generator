import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file
import pdfplumber
import docx
from werkzeug.utils import secure_filename
from groq import Groq
from fpdf import FPDF
load_dotenv()
# -----------------------------
# Groq Configuration
# -----------------------------
client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# -----------------------------
# Flask Configuration
# -----------------------------
app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['RESULTS_FOLDER'] = 'results/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()

    if ext == 'pdf':
        with pdfplumber.open(file_path) as pdf:
            text = ''.join(page.extract_text() or "" for page in pdf.pages)
        return text

    elif ext == 'docx':
        doc = docx.Document(file_path)
        return ' '.join(para.text for para in doc.paragraphs)

    elif ext == 'txt':
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()

    return None


def Question_mcqs_generator(input_text, num_questions):

    prompt = f"""
You are an expert teacher.

Generate at most {num_questions} MCQs.
Keep each question and answer concise.

TEXT:
{input_text}

Rules:
1. Every question must come only from the given text.
2. Each question must have four options.
3. Label options as A, B, C and D.
4. Mention the correct answer.
5. Keep the questions clear and concise.

Format:

## MCQ

Question:
A)
B)
C)
D)

Correct Answer:
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        max_tokens=2500
    )

    return response.choices[0].message.content


def save_mcqs_to_file(mcqs, filename):
    results_path = os.path.join(app.config['RESULTS_FOLDER'], filename)

    with open(results_path, 'w', encoding='utf-8') as f:
        f.write(mcqs)

    return results_path


def create_pdf(mcqs, filename):

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for mcq in mcqs.split("## MCQ"):
        if mcq.strip():
            pdf.multi_cell(0, 10, mcq.strip())
            pdf.ln(5)

    pdf_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    pdf.output(pdf_path)

    return pdf_path


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate_mcqs():

    if 'file' not in request.files:
        return "No file uploaded."

    file = request.files['file']

    if file.filename == "":
        return "Please select a file."

    if file and allowed_file(file.filename):

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Extract text
        text = extract_text_from_file(file_path)

        if not text:
            return "Unable to extract text from the file."

        # Limit text size
        MAX_CHARS = 2000
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS]

        # Limit MCQs
        num_questions = min(int(request.form['num_questions']), 20)

        # Generate MCQs
        mcqs = Question_mcqs_generator(text, num_questions)

        txt_filename = f"generated_mcqs_{filename.rsplit('.',1)[0]}.txt"
        pdf_filename = f"generated_mcqs_{filename.rsplit('.',1)[0]}.pdf"

        save_mcqs_to_file(mcqs, txt_filename)
        create_pdf(mcqs, pdf_filename)

        return render_template(
            'results.html',
            mcqs=mcqs,
            txt_filename=txt_filename,
            pdf_filename=pdf_filename
        )

    return "Invalid file format."


@app.route('/download/<filename>')
def download_file(filename):

    file_path = os.path.join(app.config['RESULTS_FOLDER'], filename)

    return send_file(file_path, as_attachment=True)

# Create folders if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)