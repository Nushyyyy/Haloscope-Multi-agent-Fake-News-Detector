"""
Haloscope Backend API
Flask server that exposes the analysis functionality via REST API
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import warnings
import sys
import os

# Suppress warnings
warnings.filterwarnings('ignore')
os.environ['PYTHONWARNINGS'] = 'ignore'

# Import all the haloscope code from your untitled5.py
# You can either copy the entire code here or import it as a module

# ============================================================================
# PASTE YOUR ENTIRE HALOSCOPE CODE HERE (from untitled5.py)
# Everything from "import re" to "analyze_url" function
# ============================================================================

import re
import json
import sqlite3
import time
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
import nltk

# Configuration
class Config:
    def __init__(self):
        # 🔑 PUT YOUR GEMINI API KEY HERE
        self.GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"  # Replace with your actual key
        
        self.GEMINI_MODEL = "gemini-1.5-flash"
        self.MAX_SEARCH_RESULTS = 5
        self.SEARCH_TIMEOUT = 10
        self.SOURCES_DB = "sources.db"
        self.TIMELINE_DB = "timeline.db"
        self.gemini_client = None
        self.llm_enabled = False
        
        # Try to initialize Gemini if key is provided
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """Initialize Gemini client if API key is valid"""
        if not self.GEMINI_API_KEY or self.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
            print("⚠️  No Gemini API key configured - LLM features disabled")
            return
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.GEMINI_API_KEY)
            self.gemini_client = genai.GenerativeModel(self.GEMINI_MODEL)
            self.llm_enabled = True
            print("✅ Gemini API initialized successfully")
        except Exception as e:
            print(f"⚠️  Gemini API initialization failed: {e}")
            self.llm_enabled = False

config = Config()

# Download NLTK data
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt", quiet=True)

from nltk.tokenize import sent_tokenize

# Initialize databases
def init_databases():
    conn = sqlite3.connect(config.SOURCES_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS source_ratings (
            domain TEXT PRIMARY KEY,
            credibility_score REAL,
            bias_score REAL,
            factual_reporting TEXT,
            last_updated TEXT
        )
    """)
    sources = [
        ("reuters.com", 0.95, 0.0, "VERY_HIGH", "2025-01-01"),
        ("apnews.com", 0.95, 0.0, "VERY_HIGH", "2025-01-01"),
        ("bbc.com", 0.92, 0.0, "HIGH", "2025-01-01"),
        ("wikipedia.org", 0.85, 0.0, "HIGH", "2025-01-01"),
        ("en.wikipedia.org", 0.85, 0.0, "HIGH", "2025-01-01"),
        ("nytimes.com", 0.90, 0.1, "HIGH", "2025-01-01"),
        ("cnn.com", 0.88, 0.1, "HIGH", "2025-01-01"),
        ("npr.org", 0.90, 0.0, "HIGH", "2025-01-01"),
    ]
    cursor.executemany("INSERT OR IGNORE INTO source_ratings VALUES (?,?,?,?,?)", sources)
    conn.commit()
    conn.close()

init_databases()

# Utility functions
def extract_domain(url: Optional[str]) -> str:
    if not url:
        return "unknown"
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '').lower()
        return domain if domain else "unknown"
    except:
        return "unknown"

def fetch_article(url: str) -> Optional[str]:
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        time.sleep(1)
        response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup(['script', 'style', 'noscript', 'svg', 'form', 'header', 'footer', 'nav', 'aside', 'iframe']):
            tag.decompose()
        
        content = ""
        if 'wikipedia.org' in url:
            wiki_content = soup.find('div', {'id': 'mw-content-text'})
            if wiki_content:
                content_div = wiki_content.find('div', class_='mw-parser-output')
                if content_div:
                    paragraphs = content_div.find_all('p')
                    content = '\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        if not content:
            article = soup.find('article')
            if article:
                paragraphs = article.find_all(['p', 'h1', 'h2', 'h3'])
                content = '\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        if not content:
            main = soup.find('main')
            if main:
                paragraphs = main.find_all(['p', 'h1', 'h2', 'h3'])
                content = '\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        if not content:
            paragraphs = soup.find_all('p')
            good = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50]
            content = '\n'.join(good)
        
        title = soup.title.string.strip() if soup.title else ""
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'\[edit\]', '', content)
        content = re.sub(r'\[\d+\]', '', content)
        
        full_text = f"{title}\n\n{content}".strip()
        return full_text if len(full_text) >= 100 else None
    except:
        return None

def get_source_credibility(domain: str) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(config.SOURCES_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT credibility_score, bias_score, factual_reporting FROM source_ratings WHERE domain = ?", (domain,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"credibility_score": float(row[0]), "bias_score": float(row[1]), "factual_reporting": row[2]}
    except:
        pass
    return {"credibility_score": 0.5, "bias_score": 0.0, "factual_reporting": "UNKNOWN"}

def detect_language(text: str) -> Dict[str, Any]:
    if len(text) < 10:
        return {"language": "UNKNOWN", "confidence": 0.0}
    try:
        from langdetect import detect_langs
        detections = detect_langs(text)
        if detections:
            primary = detections[0]
            return {"language": primary.lang.upper(), "confidence": round(primary.prob * 100, 2)}
    except:
        pass
    return {"language": "UNKNOWN", "confidence": 0.0}

def analyze_transparency(text: str) -> float:
    indicators = {
        "byline": bool(re.search(r'\bBy\s+[A-Z][a-zA-Z\s]+', text)),
        "date": bool(re.search(r'\b\d{4}-\d{2}-\d{2}\b', text) or re.search(r'\b[A-Z][a-z]{2,9}\s+\d{1,2},\s+\d{4}\b', text)),
        "contact": bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}', text))
    }
    return sum(indicators.values()) / 3.0

def extract_claims(text: str, max_claims: int = 5) -> List[str]:
    try:
        sentences = sent_tokenize(text)
    except:
        sentences = text.split('. ')
    
    scored = []
    for sentence in sentences:
        if len(sentence) < 20:
            continue
        score = 0
        if re.search(r'\b\d+', sentence):
            score += 2
        if any(verb in sentence.lower() for verb in ['said', 'announced', 'claimed', 'reported']):
            score += 2
        if re.search(r'\b(19|20)\d{2}\b', sentence):
            score += 1
        if score > 0:
            scored.append((score, sentence))
    
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:max_claims]]

def analyze_url(url: str) -> Dict[str, Any]:
    """Main analysis function"""
    text = fetch_article(url)
    if not text:
        return {"error": "Failed to extract content from URL"}
    
    domain = extract_domain(url)
    cred = get_source_credibility(domain)
    lang = detect_language(text)
    trans = analyze_transparency(text)
    claims = extract_claims(text, 5)
    source_score = cred["credibility_score"] * 0.7 + trans * 0.3
    
    return {
        "url": url,
        "domain": domain,
        "source_score": source_score,
        "credibility": cred,
        "language": lang,
        "claims": claims,
        "text_length": len(text)
    }

# ============================================================================
# FLASK API SETUP
# ============================================================================

app = Flask(__name__)
CORS(app)  # Enable CORS for Chrome extension

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'Haloscope API is running'})

@app.route('/analyze', methods=['POST'])
def analyze():
    """Main analysis endpoint"""
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'No URL provided'}), 400
        
        print(f"Analyzing: {url}")
        result = analyze_url(url)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🚀 HALOSCOPE API SERVER STARTING")
    print("=" * 70)
    print("\n📍 Server running on: http://127.0.0.1:5000")
    print("🔍 Health check: http://127.0.0.1:5000/health")
    print("📊 Analysis endpoint: POST http://127.0.0.1:5000/analyze")
    print("\n💡 Make sure your Chrome extension points to this URL")
    print("=" * 70 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)