import gradio as gr
import json, csv, io, sys
sys.path.insert(0, '.')
from src.scorer import score_candidate
from src.jd_config import JD_PROFILE
from src.reranker import rerank_and_explain

def rank_candidates(jsonl_text):
    try:
        candidates = [json.loads(l) for l in jsonl_text.strip().split('\n') if l.strip()]
        scored = [r for c in candidates if (r := score_candidate(c, JD_PROFILE))]
        if not scored:
            return "No candidates passed the filter. Check your input format."
        scored.sort(key=lambda x: -x['composite_score'])
        k = min(len(scored), 10)
        final = rerank_and_explain(scored[:k], JD_PROFILE, final_k=k)
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(['rank', 'candidate_id', 'score', 'reasoning'])
        for i, r in enumerate(final, 1):
            w.writerow([i, r['candidate_id'], round(r['composite_score'], 4), r['reasoning']])
        return out.getvalue()
    except Exception as e:
        return f"Error: {str(e)}"

demo = gr.Interface(
    fn=rank_candidates,
    inputs=gr.Textbox(
        label="Paste candidate JSONL (one JSON per line)",
        lines=10,
        placeholder='{"candidate_id": "CAND_0000001", "profile": {...}, ...}'
    ),
    outputs=gr.Textbox(label="Ranked Output CSV", lines=15),
    title="Redrob Candidate Ranker",
    description="Paste candidate profiles in JSONL format. Returns ranked shortlist with reasoning."
)

demo.launch()