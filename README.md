# 🌈 Groq Vision – Modular Batch MCQ Extractor

<div align="center">
  <img src="https://raw.githubusercontent.com/your-username/Groq_Vision/main/docs/screenshot.png" alt="App screenshot" width="850"/>
</div>

> **Extract MCQs from a batch of scanned images in seconds and export them to a beautifully styled PDF.**

---

## ✨ Quick facts
| Feature | Details |
|--------|---------|
| **Framework** | Streamlit (interactive UI) |
| **Vision model** | Groq `meta‑llama/llama‑4‑scout‑17b‑16e‑instruct` |
| **Modular codebase** | `app.py` (entry point) + `src/` package (config, services, UI) |
| **Rate‑limit safety** | 3 s delay ⇒ ≤ 30 RPM, ≤ 30 K TPM (Groq limits) |
| **PDF themes** | Light / Dark (custom fonts & colours) |
| **Upload limit** | 30 images per session (PNG, JPG, JPEG) |
| **Environment** | Python 3.9+, virtual‑env (`venv/`) |
| **License** | MIT |

---

## 📚 Table of Contents
1. [Why modular?](#why-modular)  
2. [Installation](#installation)  
3. [Configuration](#configuration)  
4. [Running the app](#running-the-app)  
5. [Technical deep‑dive](#technical-deep-dive)  
6. [Project structure](#project-structure)  
7. [Extending & contributing](#extending--contributing)  
8. [License](#license)

---

## 🧩 Why modular?
The original **`test.py`** script worked but mixed UI, service logic, and helpers in a single file – making testing, reuse, and future extension painful.  

The new layout isolates concerns:
- **`src/config.py`** – centralized settings (API key, model name, limits, PDF defaults).
- **`src/groq_service.py`** – Groq client creation, prompt building, and batch extraction.
- **`src/pdf_service.py`** – all ReportLab PDF generation utilities.
- **`src/file_utils.py`** – temporary‑file handling for uploads and cleanup.
- **`src/ui.py`** – Streamlit UI orchestration (upload, progress, PDF download).
- **`app.py`** – tiny entry point that simply calls `run_app()`.

> **Result:** cleaner imports, easier unit‑testing, and a clear separation of *what* the app does from *how* it does it.

The legacy `test.py` is now **ignored** via `.gitignore` and **never committed**.

---

## 🛠️ Installation
```bash
# Clone the repo
git clone https://github.com/your-username/Groq_Vision.git
cd Groq_Vision

# Create & activate a virtual environment (PowerShell shown)
python -m venv venv
.\venv\Scripts\Activate.ps1  # or `source venv/bin/activate` on *nix

# Install dependencies
pip install -r requirements.txt
```
> The repository already ships a pre‑built `venv/` for reproducibility – you may simply activate it and skip the `pip install` step.

---

## 🔧 Configuration
Create a **`.env`** file at the repository root (same folder as `app.py`):
```dotenv
# .env – keep this file private!
GROQ_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
`python‑dotenv` loads this file automatically; the key is accessed in `src/config.py`.

> **Security note:** `.env` is listed in `.gitignore` alongside `test.py`, so it will never be pushed.

---

## ▶️ Running the app
```bash
# From the repo root
streamlit run app.py
```
The UI appears at `http://localhost:8501`.

### Typical workflow
1. **Upload** up to 30 images (PNG/JPG).  
2. Click **“Extract MCQs”** – a progress bar shows per‑image status.  
3. After extraction, pick a **PDF name** and a **theme** (Light/Dark).  
4. Click **“Generate & Download PDF”** – the file streams straight to your browser.

---

## 🧠 Technical deep‑dive
### 1️⃣ Configuration (`src/config.py`)
```python
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_IMAGES = 30
DELAY_SECONDS = 3  # respects Groq rate limits
DEFAULT_PDF_NAME = "Extracted_MCQs"
PDF_THEMES = ["Light", "Dark"]
```
All magic numbers live here – change them in one place.

### 2️⃣ Groq service (`src/groq_service.py`)
- **Client init** – raises a clear `ValueError` if the API key is missing.
- **`encode_image_to_base64`** – pure utility.
- **`build_mcq_prompt`** – a **strict, no‑hallucination** prompt (see lines 48‑73) that forces the model to output *exactly* what it sees, never inventing answers.
- **`extract_mcq_with_groq`** – calls `client.chat.completions.create` with:
  - `temperature=0` (deterministic),
  - `max_completion_tokens=4096`,
  - a multimodal payload (`type: "image_url"`).
- **`process_images`** – simple loop over image paths, applying the extraction function and collecting results.

### 3️⃣ PDF service (`src/pdf_service.py`)
- Uses **ReportLab**’s `SimpleDocTemplate`.
- Dynamically switches fonts, colours, and a **dark‑background canvas** (`add_dark_background`).
- Builds a **story** list of `Paragraph`, `Spacer`, and `HRFlowable` elements.  
- Sanitises text (`&`, `<`, `>`) and converts newlines to `<br/>` for proper rendering.

### 4️⃣ File utilities (`src/file_utils.py`)
- `save_uploaded_file_to_temp` – writes a Streamlit `UploadedFile` to a temp file and returns its path.
- `cleanup_temp_files` – idempotent removal of temp files.
- `get_temp_pdf_path` – resolves a safe temporary path for the output PDF.

### 5️⃣ UI orchestration (`src/ui.py` – omitted for brevity but orchestrates the flow):
- Handles the Streamlit sidebar, uploader, progress bar, status messages, and download button.
- Calls the services in this order:
  1. `save_uploaded_file_to_temp` for each upload.
  2. `groq_service.process_images` (rate‑limited via `DELAY_SECONDS`).
  3. Stores results in `st.session_state`.
  4. `pdf_service.create_pdf` to produce the final document.
  5. Streams the PDF back to the user.

All **stateful** objects live in Streamlit’s `session_state`, guaranteeing that a rerun of the script (triggered by UI interaction) does **not** re‑process already‑extracted images.

---

## 📂 Project structure
```
Groq_Vision/
├─ app.py                 # tiny entry point → src.ui.run_app()
├─ .gitignore             # ignores test.py, .env, __pycache__
├─ .env.example           # template for the required secret key
├─ requirements.txt       # pinned dependencies
├─ README.md              # <-- you are reading it!
├─ src/                    # <--- modular core
│   ├─ __init__.py
│   ├─ config.py          # global settings & limits
│   ├─ groq_service.py    # Vision client & extraction logic
│   ├─ pdf_service.py     # ReportLab PDF builder
│   ├─ file_utils.py      # temporary‑file helpers
│   └─ ui.py              # Streamlit UI orchestration
└─ docs/
    └─ screenshot.png     # demo image used in this README
```
`test.py` is **not** version‑controlled (see `.gitignore`).

---

## 🤝 Extending & contributing
- **Feature ideas** (open an issue first):
  - Fallback OCR (e.g., Tesseract) when Groq fails.
  - Accept PDF uploads and split them into pages automatically.
  - Export results as JSON/CSV in addition to PDF.
  - Parallelise API calls while preserving the 30 RPM quota.
- **Development workflow**
  ```bash
  git checkout -b feature/awesome-feature
  # edit code, run `streamlit run app.py` to test
  git commit -am "Add awesome feature"
  git push origin feature/awesome-feature
  # create a Pull Request on GitHub
  ```
- **Testing** – add unit tests under a `tests/` folder. Mock the Groq client (`unittest.mock`) to avoid network calls.
- **Style** – the project follows **PEP 8**; run `ruff` or `black` before committing.

---

## 📄 License

This project is released under the **MIT License** – see the `LICENSE` file for the full text.

---

*Happy extracting! 🎉*