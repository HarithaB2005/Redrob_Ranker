import gradio as gr
import json, csv, io, sys
sys.path.insert(0, '.')
from src.scorer import score_candidate
from src.jd_config import JD_PROFILE
from src.reranker import rerank_and_explain

def rank_sample(jsonl_text):
    candidates = [json.loads(l) for l in jsonl_text.strip().split('\n') if l.strip()]
    scored = [r for c in candidates if (r := score_candidate(c, JD_PROFILE))]
    scored.sort(key=lambda x: -x['composite_score'])
    final = rerank_and_explain(scored[:min(len(scored),10)], JD_PROFILE, final_k=min(len(scored),10))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['rank','candidate_id','score','reasoning'])
    for i, r in enumerate(final, 1):
        w.writerow([i, r['candidate_id'], round(r['composite_score'],4), r['reasoning']])
    return out.getvalue()

gr.Interface(fn=rank_sample,
             inputs=gr.Textbox(label="Paste JSONL candidates (one per line)", lines=10),
             outputs=gr.Textbox(label="Ranked output CSV"),
             title="Redrob Candidate Ranker Demo").launch()
