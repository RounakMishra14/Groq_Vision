# Groq Vision - Intelligent MCQ Extraction System

> **A production-ready Streamlit application that leverages Groq Vision to accurately extract Multiple Choice Questions (MCQs) from images using dynamic image preprocessing, perspective correction, intelligent screen detection, and structured PDF generation.**

<p align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-Web_App-red.svg)
![Groq](https://img.shields.io/badge/Groq-Llama_4_Scout-green.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-Image_Processing-orange.svg)
![Pillow](https://img.shields.io/badge/Pillow-Imaging-yellow.svg)
![SQLite](https://img.shields.io/badge/SQLite-Database-blue.svg)


</p>

---

# Overview

Groq Vision is an end-to-end intelligent MCQ extraction application designed to solve a common problem encountered while digitizing examination materials.

Instead of relying on traditional OCR engines alone, this project utilizes **Groq Vision (Llama-4-Scout Vision)** to understand entire question papers directly from images and generate structured, well-formatted MCQs.

The application has been engineered with several preprocessing stages that significantly improve extraction quality while reducing unnecessary visual information before the image reaches the Vision model.

The result is a fast, reliable, production-ready system capable of extracting hundreds of MCQs into beautifully formatted PDFs.

---

# Features

* User Authentication System
* Secure Password Storage
* Encrypted Groq API Keys
* Batch Image Upload
* Dynamic White Screen Detection
* Automatic Perspective Correction
* Intelligent Cropping
* Optional Image Compression
* Usage Dashboard
* Token Usage Statistics
* PDF Export
* Light/Dark PDF Themes
* Processing Logs
* Error Handling
* Streamlit Web Interface
* SQLite Database
* Modular Project Structure

---

# Application Workflow

```
                    User Login
                         │
                         ▼
              Upload MCQ Images
                         │
                         ▼
         Detect White Display Region
                         │
                         ▼
          Perspective Transformation
                         │
                         ▼
            Intelligent Cropping
                         │
                         ▼
           Optional Compression
                         │
                         ▼
               Groq Vision API
                         │
                         ▼
          Structured MCQ Extraction
                         │
                         ▼
         Beautiful PDF Generation
```

---

# Project Architecture

```
                  ┌──────────────────────┐
                  │     Streamlit UI      │
                  └──────────┬────────────┘
                             │
             ┌───────────────┼────────────────┐
             ▼               ▼                ▼

      Authentication     Image Engine     PDF Service

             │               │                │

             ▼               ▼                ▼

        SQLite DB     Groq Vision API    ReportLab

             │               │                │

             └───────────────┼────────────────┘
                             ▼
                    Final PDF Output
```

---

# Project Structure

```
Groq_Vision/

│
├── app.py
├── requirements.txt
├── README.md
│
├── src/
│   ├── ui.py
│   ├── database.py
│   ├── auth.py
│   ├── encryption.py
│   ├── image_processor.py
│   ├── groq_service.py
│   ├── pdf_service.py
│   ├── usage_tracker.py
│   ├── logger.py
│   ├── config.py
│   ├── file_utils.py
│   └── utils.py
│
├── database/
│
├── logs/
│
├── assets/
│
└── temp/
```

---

# Image Processing Pipeline

One of the biggest improvements made during development was minimizing irrelevant image content before sending it to the Vision model.

Instead of uploading the entire photograph, only the display region containing the actual questions is extracted.

```
Original Image

      │

      ▼

White Pixel Detection

      │

      ▼

Largest Bright Region

      │

      ▼

Perspective Detection

      │

      ▼

Perspective Warp

      │

      ▼

Safety Expansion

      │

      ▼

Final Cropped Image

      │

      ▼

Groq Vision
```

---

# Dynamic White Screen Detection

Unlike fixed cropping techniques, this project dynamically detects the display region.

The algorithm works by:

* Converting image to HSV
* Detecting high brightness pixels
* Rejecting highly saturated colors
* Removing noise using morphology
* Finding the largest valid contour
* Approximating four corner points
* Performing perspective correction
* Expanding boundaries slightly to avoid clipping text

Advantages:

* Works with tilted screens
* Handles different laptop sizes
* Ignores keyboard/background
* Eliminates unnecessary visual noise
* Reduces irrelevant pixels before Vision processing

---

# Perspective Correction

Images captured from mobile phones often contain perspective distortion.

Instead of sending skewed images to the model, a four-point perspective transformation is applied.

Benefits:

* Straightened text
* Better readability
* Improved OCR quality
* Better Vision understanding
* Consistent input dimensions

---

# Intelligent Cropping

The crop is intentionally expanded by a small configurable safety margin.

Reason:

If the crop is too tight, question numbers or option labels located near image edges may get clipped.

The expansion balances:

* Maximum content retention
* Minimum unnecessary pixels

---

# Compression Research

A significant portion of development was dedicated to understanding how image compression affects Groq Vision.

Hundreds of images were tested across multiple compression levels.

The experiments compared:

* JPEG Quality
* Image Resolution
* Token Usage
* OCR Accuracy
* Processing Time

---

# Major Research Finding

One surprising observation was:

> **Reducing file size alone does NOT significantly reduce Groq Vision token consumption.**

JPEG compression dramatically reduces storage size but contributes very little to token reduction.

Instead, token usage depends primarily on:

* Visible content
* Image dimensions
* Amount of text
* Complexity of the scene

---

# Compression Results

| Technique              | File Size | Token Reduction |
| ---------------------- | --------- | --------------- |
| JPEG Quality Reduction | ⭐⭐⭐⭐⭐     | ⭐               |
| Resize Only            | ⭐⭐⭐       | ⭐⭐              |
| Screen Cropping        | ⭐⭐        | ⭐⭐⭐⭐⭐           |
| Perspective Correction | ⭐         | ⭐⭐⭐⭐            |
| Remove Background      | ⭐         | ⭐⭐⭐⭐⭐           |

Conclusion:

Cropping unnecessary pixels is substantially more beneficial than aggressively compressing JPEG quality.

---

# Why Cropping Matters More

Consider two images.

Image A

```
Entire Laptop
Keyboard
Desk
Background
Screen
```

Image B

```
Only Screen
```

Although Image B may only be 20–30% smaller in file size, the Vision model processes significantly fewer irrelevant visual elements.

This leads to:

* Better extraction
* Faster processing
* Lower effective visual complexity
* Improved consistency

---

# Prompt Engineering

The prompt supplied to Groq Vision has been carefully designed to minimize hallucinations.

Core rules include:

* Never invent text
* Never infer answers
* Preserve numbering
* Preserve option labels
* Preserve formatting
* Return only visible information
* Mark unreadable text as `[UNCLEAR]`
* Never solve questions

This dramatically improves extraction reliability.

---

# Groq Vision Integration

Model Used

```
meta-llama/llama-4-scout-17b-16e-instruct
```

Parameters

```
Temperature : 0

Top P : 1

Streaming : Disabled

Max Completion Tokens : 4096
```

The deterministic configuration ensures highly repeatable outputs.

---

# Usage Tracking

The application records processing statistics including:

* Prompt Tokens
* Completion Tokens
* Total Tokens
* Processing Duration
* Daily Usage
* Requests Per Minute
* Tokens Per Minute
* API Errors
* Rate Limits

This helps monitor API consumption efficiently.

---

# Authentication

Each user has:

* Login
* Password
* Encrypted API Key
* Personal Usage Statistics

Passwords are securely hashed before storage.

---

# Security

Security features include:

* SQLite authentication
* Password hashing
* Fernet encryption
* Environment variables
* API key isolation
* Session validation

---

# PDF Generation

The generated PDF contains:

* Custom Title
* Extraction Timestamp
* Image-wise Organization
* Structured Questions
* Multiple Themes
* Clean Typography
* Horizontal Separators

Supported Themes:

* Light
* Dark

---

# Performance Optimizations

Implemented optimizations include:

* Dynamic cropping
* Perspective correction
* Optional compression
* Temporary file cleanup
* Cached resources
* Modular architecture
* Efficient API usage
* Progress tracking

---

# Installation

Clone the repository

```bash
git clone https://github.com/your_username/Groq_Vision.git
```

Enter the project

```bash
cd Groq_Vision
```

Install dependencies

```bash
pip install -r requirements.txt
```

Create a `.env`

```
GROQ_API_KEY=your_api_key
```

Run

```bash
streamlit run app.py
```

---

# Technologies Used

| Technology   | Purpose            |
| ------------ | ------------------ |
| Python       | Backend            |
| Streamlit    | UI                 |
| Groq API     | Vision Model       |
| OpenCV       | Image Processing   |
| Pillow       | Image Manipulation |
| SQLite       | User Database      |
| ReportLab    | PDF Generation     |
| Cryptography | API Encryption     |

---

# Future Improvements

* Multi-language OCR
* Automatic answer key generation
* Image quality scoring
* Duplicate question detection
* Parallel API processing
* Local Vision Model Support
* Cloud Deployment
* Batch ZIP processing
* Markdown export
* DOCX export
* Searchable PDF generation

---

# Lessons Learned

This project highlighted several practical insights regarding Vision-language models:

* Effective preprocessing often provides greater benefits than increasing model complexity.
* Reducing irrelevant visual content improves extraction quality more than aggressive JPEG compression.
* Perspective correction substantially enhances readability for photographed documents.
* Carefully constrained prompts significantly reduce hallucinations in structured extraction tasks.
* Monitoring token usage and rate limits is essential for reliable production deployments.

---

# Contributing

Contributions are welcome.

If you have ideas for improving preprocessing, OCR accuracy, token optimization, or PDF formatting, feel free to open an issue or submit a pull request.

---

## 📜 License

Copyright © 2026 Rounak Mishra

This project is published for portfolio and educational purposes only.

All rights reserved.

No part of this repository may be copied, modified, redistributed, or used commercially without the prior written permission of the author.

# Acknowledgements

Special thanks to the developers and communities behind:

* Groq
* Meta Llama
* Streamlit
* OpenCV
* Pillow
* ReportLab
* SQLite
* Python

---

<p align="center">

### ⭐ If you found this project useful, consider giving it a Star on GitHub!

**Built with Python ❤️ and Groq Vision**

</p>
