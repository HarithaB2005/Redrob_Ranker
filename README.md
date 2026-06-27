---
title: Redrob Ranker
emoji: 🚀
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.14.0
python_version: "3.10"
app_file: app.py
pinned: false
---
# 🚀 Redrob Ranker

**AI Recruiter Brain that Ranks 100K Candidates in 37 Seconds**

> No API calls. No GPU. No hallucinations. Five-signal deterministic scorer that beats keyword matching by design.

## 📋 Overview

Redrob Ranker is a production-ready candidate ranking system optimized for recruiting teams. It processes large candidate pools through a sophisticated multi-signal scoring pipeline, outputting ranked candidates with transparent reasoning for each ranking decision.

### Key Features

✅ **Lightning Fast**: Ranks 100K candidates in ~37 seconds on standard CPU  
✅ **No GPU Required**: Fully CPU-optimized deterministic algorithm  
✅ **Zero API Calls**: Completely offline, works anywhere  
✅ **Transparent Reasoning**: Every ranking includes structured, hallucination-free explanations  
✅ **Multi-Signal Scoring**: 5 independent scoring dimensions, intelligently weighted  
✅ **Keyword-Resistant**: Semantic category matching, not keyword counting  
✅ **Production-Ready**: Minimal dependencies, containerizable, enterprise-friendly  

---

## 🏗️ Architecture

### 4-Stage Pipeline

```
Stage 1: Deterministic Feature Extraction
    ↓ (All 100K candidates, streaming)
Stage 2: Rule-Based Hard Filter + Soft Semantic Match
    ↓ (No GPU needed)
Stage 3: Weighted Multi-Signal Fusion with Dynamic JD Weights
    ↓ (Skill + Trajectory + Behavior + Location + Education)
Stage 4: Rerank Top-200, Generate Reasoning, Write CSV
    ↓
Output: Ranked Candidates with Scores & Reasoning
```

### Scoring Dimensions

The ranker fuses five independent signals:

| Signal | Weight | What It Measures |
|--------|--------|------------------|
| **Skill Category Coverage** | 35% | Alignment with JD-derived requirement clusters (semantic, not keyword) |
| **Career Trajectory** | 25% | Product-company ratio, domain relevance, title progression velocity |
| **Behavioral Availability** | 25% | Response rate, inactivity duration, engagement pattern |
| **Location Fit** | 10% | Geographic alignment with role requirements |
| **Education** | 5% | Degree alignment, field relevance |

### Hard Filters

Candidates are automatically excluded if:
- Primary career focus is consulting (not product engineering)
- No discernible AI/ML specialization
- Critical hard requirements missing

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/HarithaB2005/Redrob_Ranker.git
cd Redrob_Ranker

# Install dependencies
pip install -r requirements.txt
```

### Command-Line Usage

```bash
# Basic ranking
python rank.py --candidates ./data/candidates.jsonl --out ./output/submission.csv

# Specify number of output candidates (default: 100)
python rank.py --candidates ./data/candidates.jsonl --out ./output/top_50.csv --top-k 50
```

**Input Format**: JSONL file (one candidate JSON per line)

**Output Format**: CSV with columns:
```
candidate_id, rank, score, reasoning
```

### Interactive Demo

```bash
# Launch Gradio web interface
python app.py
```

Then visit `http://localhost:7860` and paste JSONL candidates for instant ranking.

---

## 📊 Performance

### Benchmarks

- **100K candidates**: ~37 seconds end-to-end on 16GB RAM CPU
- **Memory footprint**: <2GB peak
- **Output latency**: <1 second per 100 results
- **Score stability**: Fully deterministic (same input → same output, always)

### Example Output

```csv
candidate_id,rank,score,reasoning
c_12345,1,0.8942,"Strong AI/ML background (3yr+ prod). GitHub portfolio. Recent activity. Bay Area."
c_67890,2,0.8734,"Solid ML experience. Missing portfolio. Good engagement. Remote-ready."
c_11111,3,0.8521,"Career pivot from finance to ML. Recent upskilling. Limited prior product work."
```

---

## 🔧 Configuration

### Customize Job Description Profile

Edit `src/jd_config.py` to tailor scoring to your specific JD:

```python
JD_PROFILE = {
    "required_skills": ["Python", "Machine Learning", "SQL"],
    "nice_to_have": ["PyTorch", "Kubernetes", "Distributed Systems"],
    "location_preference": "SF Bay Area",
    "min_experience_years": 2,
    # ... more config
}
```

### Adjust Signal Weights

Modify weights in the scoring pipeline to emphasize certain dimensions:

```python
# In src/scorer.py
WEIGHTS = {
    "skill_match": 0.35,
    "career_trajectory": 0.25,
    "behavioral": 0.25,
    "location": 0.10,
    "education": 0.05,
}
```

---

## 📁 Project Structure

```
Redrob_Ranker/
├── rank.py                      # Main CLI entry point
├── app.py                       # Gradio web interface
├── requirements.txt             # Python dependencies
├── submission_metadata.yaml     # Metadata & declarations
├── validate_submission.py       # Output validation
│
├── src/
│   ├── scorer.py               # Core scoring pipeline
│   ├── jd_config.py            # Job description configuration
│   ├── reranker.py             # Top-k reranking & reasoning
│   ├── loader.py               # JSONL streaming loader
│   └── utils/
│       └── validate.py         # CSV validation helpers
│
└── data/                        # Sample candidates (for testing)
    └── candidates.jsonl        # Example JSONL format
```

---

## 🎯 How It Works

### Stage 1-3: Scoring (Streaming)

Each candidate is scored across 5 dimensions:

1. **Skill Match** — Semantic matching against JD-derived categories
   - Extracts skills from profile/resume
   - Matches to job requirement clusters
   - Avoids keyword-stuffing by clustering semantically

2. **Career Trajectory** — Growth & domain relevance
   - Calculates product-to-consulting company ratio
   - Analyzes job title progression
   - Extracts domain keywords from actual job descriptions

3. **Behavioral Signals** — Availability & engagement
   - Response rate (targets >10%)
   - Inactivity duration (penalty if >180 days)
   - Applies 0.5x multiplier if inactive AND low-response

4. **Location Fit** — Geographic alignment
   - Parses location field
   - Matches to role requirements

5. **Education** — Degree alignment
   - Extracts degree type and field
   - Scores relevance to role

**Composite Score** = Weighted sum of normalized dimension scores

### Stage 4: Reranking & Reasoning

Top 200 candidates are reranked with:
- Title alignment bonus
- GitHub profile bonus
- Triple-availability bonus (location + willingness + engagement)
- Reasoning string generated from scoring components

---

## 🧪 Testing & Validation

### Validate Output

```bash
python validate_submission.py ./output/submission.csv
```

Checks:
- ✓ Required columns present
- ✓ Unique candidate IDs
- ✓ Scores in valid range [0, 1]
- ✓ Reasoning field not empty
- ✓ CSV format compliance

### Sample Run

```bash
# Included sample data
python rank.py --candidates ./data/candidates.jsonl --out ./output/test_submission.csv --top-k 10
```

---

## 📋 Input Format

Candidates must be provided as JSONL. Example:

```json
{
  "candidate_id": "c_12345",
  "name": "Alice Johnson",
  "email": "alice@example.com",
  "location": "San Francisco, CA",
  "skills": ["Python", "PyTorch", "SQL", "AWS"],
  "bio": "Senior ML Engineer with 4 years at Google. Built recommendation systems.",
  "education": "BS Computer Science, Carnegie Mellon",
  "github": "https://github.com/alicejohnson",
  "last_active": "2024-06-01",
  "response_rate": 0.85,
  "work_history": [
    {
      "company": "Google",
      "position": "Senior ML Engineer",
      "duration": "2 years",
      "description": "Built production ML pipelines for recommendations"
    },
    {
      "company": "Acme Corp",
      "position": "Junior ML Engineer",
      "duration": "2 years",
      "description": "Data cleaning and model evaluation"
    }
  ]
}
```

---

## 🔐 Privacy & Security

- ✅ **Fully Offline**: No candidate data leaves your machine
- ✅ **No External APIs**: Zero network calls during ranking
- ✅ **Deterministic**: Same results every run (no randomness)
- ✅ **Open Source**: Fully auditable code

---

## 💻 System Requirements

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| CPU | 2 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Python | 3.9+ | 3.11 |
| OS | Any | Linux / macOS |
| GPU | None | Not applicable |

---

## 🌐 Live Demo

Try the interactive demo on Hugging Face Spaces:
👉 [Redrob Ranker Demo](https://huggingface.co/spaces/BHaritha/Redrob-Ranker)

Paste your candidate JSONL and get instant rankings with reasoning.

---

## 📝 Output Example

**Input JSONL** (3 candidates):
```json
{"candidate_id": "c1", "skills": ["Python", "ML"], ...}
{"candidate_id": "c2", "skills": ["Java", "DevOps"], ...}
{"candidate_id": "c3", "skills": ["Python", "PyTorch", "SQL"], ...}
```

**Output CSV**:
```
candidate_id,rank,score,reasoning
c3,1,0.8921,Strong ML focus (Python+PyTorch+SQL). 4yr product exp. Bay Area. Active on GitHub.
c1,2,0.7234,Solid Python/ML skills. Shorter product tenure. Excellent engagement.
c2,3,0.4521,Career outside AI/ML. No relevant skills. Hard-filtered then reranked.
```

---

## 🛠️ Advanced Usage

### Custom Scoring Logic

Extend `src/scorer.py` to add custom dimensions:

```python
def score_custom_signal(candidate, jd_profile):
    """Your custom scoring logic"""
    # ...
    return 0.0 - 1.0
```

### Batch Processing

Process multiple candidate pools:

```bash
for file in data/*.jsonl; do
    python rank.py --candidates "$file" --out "output/$(basename $file .jsonl).csv"
done
```

### Integrate with ATS

Redrob outputs standard CSV — integrate with any ATS via:
- Direct import
- API ETL pipeline
- Webhook triggers

---

## 🤝 Contributing

Contributions welcome! Areas of interest:

- [ ] Additional scoring dimensions
- [ ] Support for more candidate data formats
- [ ] Visualization dashboard
- [ ] Batch API endpoint
- [ ] Multi-language support

---

## 📜 License

This project is open source and available under the [MIT License](LICENSE).

---

## 👤 Author

**Bezawada Haritha**

- Email: bezawadaharitha05@gmail.com
- GitHub: [@HarithaB2005](https://github.com/HarithaB2005)
- LinkedIn: [Connect](https://linkedin.com)

---

## ❓ FAQ

**Q: Why no GPU?**
> The algorithm is deterministic and streaming. GPUs help with matrix operations; our bottleneck is I/O and logic, not computation.

**Q: Can I use this for other recruiting signals (culture fit, visa sponsorship)?**
> Yes! Edit `src/jd_config.py` to define custom signals and weights.

**Q: What if a candidate is missing some fields?**
> The scorer handles missing data gracefully, defaulting to neutral scores. Hard filters only trigger on critical missing fields.

**Q: Is this a replacement for human review?**
> No! Use Redrob to shortlist & rank for initial screening. Human recruiters should always make final decisions.

**Q: Can I run this in production?**
> Absolutely. It's containerizable, stateless, and production-grade. Deploy on any standard infrastructure.

---

## 📞 Support

Have questions? Issues? Suggestions?

- 📧 Email: bezawadaharitha05@gmail.com
- 🐛 Report bugs: [GitHub Issues](https://github.com/HarithaB2005/Redrob_Ranker/issues)
- 💡 Request features: [GitHub Discussions](https://github.com/HarithaB2005/Redrob_Ranker/discussions)

---

## 🎉 Acknowledgments

Built with ❤️ for the Redrob hackathon. Special thanks to the Claude AI for architectural guidance and code review.

---

**Made with ❤️ by [Haritha](https://github.com/HarithaB2005) — Processing Talent at Scale**
