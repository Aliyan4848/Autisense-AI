# AutiSense AI — Hugging Face Spaces Deployment
import os, time, whisper, re, math
import gradio as gr
from gtts import gTTS
from groq import Groq
from collections import Counter

# --- SETUP ---
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)
stt_model = whisper.load_model("tiny")

# --- BUILT-IN STRATEGY KB ---
STRATEGY_KB = {
    "emotional": "Validate the feeling first, then gently suggest a calming activity or sensory break.",
    "social":    "Use simple 'I feel' statements and explain social cues in concrete, literal terms.",
    "functional":"Use 'First/Then' logic and offer two specific choices so the child can decide.",
    "crisis":    "Stay calm and use very few words — one short instruction at a time.",
}

DAILY_TASKS = ["Brush Teeth", "Breakfast", "Lunch", "Playing Game", "Dinner", "Sleep"]
TASK_STEPS  = {
    "Brush Teeth":  ["1. Put paste on brush.", "2. Brush all teeth.", "3. Rinse your mouth."],
    "Breakfast":    ["1. Sit at the table.",   "2. Eat your food.",   "3. Drink your water."],
    "Playing Game": ["1. Pick a toy.",          "2. Play nicely.",     "3. Clean up when done."],
    "Lunch":        ["1. Wash hands.",          "2. Eat your lunch.",  "3. Put your plate away."],
    "Dinner":       ["1. Sit with family.",     "2. Try your food.",   "3. Wipe your face."],
    "Sleep":        ["1. Put on pajamas.",      "2. Get in bed.",      "3. Close your eyes."]
}

# ---------------------------------------------------------------------------
# PHASE A — COMMUNICATION COACHING LABEL SYSTEM
# ---------------------------------------------------------------------------

def build_coaching_label(text: str, state: str, coaching: str | None) -> str:
    if coaching:
        return coaching
    t = text.strip().lower()
    if state == "crisis":
        return "💬 Try saying: 'I need help please.' That helps people understand you better!"
    if state == "emotional":
        if len(t.split()) <= 3:
            return "💬 Good start! Can you say more? Example: 'I feel sad because I am tired.'"
        elif "because" in t or "when" in t:
            return "⭐ Excellent! Explaining WHY you feel something is great communication!"
        else:
            return "👍 Good job sharing your feelings! Try adding 'because' to explain more."
    if state == "functional":
        if "please" not in t:
            return "💡 Tip: Adding 'please' makes your request very polite! Try it next time."
        else:
            return "⭐ Wonderful manners! Saying 'please' is so polite!"
    if state == "social":
        words = t.split()
        if len(words) <= 2:
            return "💬 Try using a full sentence! Example: 'I want to talk to you please.'"
        elif "?" in text:
            return "👍 Great — asking questions is a wonderful way to talk to people!"
        else:
            return "😊 Nice talking! Remember you can ask questions too."
    return "😊 Keep talking — you are doing great!"

# ---------------------------------------------------------------------------
# SCENARIO PROFILES
# ---------------------------------------------------------------------------
SCENARIO_PROFILES = {
    "parent": {
        "greeting":   "Switched to Parent Mode 🏠 — warm and nurturing.",
        "role":       "You are a loving, nurturing parent speaking gently to your child who has autism.",
        "tone":       "Warm, soft, and reassuring. Use pet names like 'sweetheart' or 'little one' occasionally.",
        "structure":  "Lead with emotional connection before practical help. Mirror the child's feeling first.",
        "vocabulary": "Very simple everyday words. Short sentences. No instructions longer than 5 words.",
        "examples":   (
            "Child: I feel sad. → You: Aw, I'm so sorry sweetheart. Want a big hug?\n"
            "Child: I am hungry. → You: Okay! Let's find you something yummy to eat.\n"
            "Child: I am hurt. → You: Oh no! Let me see. I'll help you feel better right away."
        ),
    },
    "teacher": {
        "greeting":   "Switched to Teacher Mode 🏫 — structured and encouraging.",
        "role":       "You are Ms. Anna, a kind and structured special-education teacher.",
        "tone":       "Calm, clear, and encouraging. Professional but warm. Praise effort explicitly.",
        "structure":  "Use step-by-step language. Give one clear instruction at a time. Acknowledge completion.",
        "vocabulary": "Simple but slightly more structured than parent mode. Use 'first', 'next', 'well done'.",
        "examples":   (
            "Child: I feel sad. → You: I see you feel sad. First, take a deep breath. Well done.\n"
            "Child: I am hungry. → You: Okay! First, let's finish this, then we'll have a snack.\n"
            "Child: I am hurt. → You: I see you're hurt. First, tell me where. I will help you."
        ),
    },
    "caretaker": {
        "greeting":   "Switched to Caretaker Mode 🤝 — calm and direct.",
        "role":       "You are a calm, patient professional caretaker supporting a child with autism.",
        "tone":       "Steady, neutral, and reassuring. No excessive emotion. Direct and clear.",
        "structure":  "Be practical and action-focused. Offer two clear options. Avoid open-ended questions.",
        "vocabulary": "Short, literal, concrete words only. No metaphors. No idioms.",
        "examples":   (
            "Child: I feel sad. → You: I hear you. Do you want to sit quietly or go for a walk?\n"
            "Child: I am hungry. → You: Got it. Do you want an apple or a sandwich?\n"
            "Child: I am hurt. → You: I'll help. Show me where it hurts."
        ),
    },
}

# ---------------------------------------------------------------------------
# EMOTION CARDS
# ---------------------------------------------------------------------------
def _svg(bg, stroke, eyes, mouth, extra, label):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120" width="84" height="100">
  <circle cx="50" cy="50" r="36" fill="{bg}" stroke="{stroke}" stroke-width="2.5"/>
  <ellipse cx="14" cy="50" rx="5" ry="8" fill="{bg}" stroke="{stroke}" stroke-width="2"/>
  <ellipse cx="86" cy="50" rx="5" ry="8" fill="{bg}" stroke="{stroke}" stroke-width="2"/>
  {eyes}{mouth}{extra}
  <text x="50" y="108" text-anchor="middle"
        font-family="Arial Rounded MT Bold,Arial,sans-serif"
        font-size="12" font-weight="bold" fill="#222">{label}</text>
</svg>"""

_EO = """<circle cx="34" cy="44" r="6" fill="white" stroke="#333" stroke-width="1.8"/>
  <circle cx="66" cy="44" r="6" fill="white" stroke="#333" stroke-width="1.8"/>
  <circle cx="35" cy="45" r="3" fill="#333"/><circle cx="67" cy="45" r="3" fill="#333"/>
  <circle cx="36" cy="43" r="1" fill="white"/><circle cx="68" cy="43" r="1" fill="white"/>"""

_EW = """<circle cx="34" cy="44" r="8" fill="white" stroke="#333" stroke-width="1.8"/>
  <circle cx="66" cy="44" r="8" fill="white" stroke="#333" stroke-width="1.8"/>
  <circle cx="34" cy="45" r="5" fill="#333"/><circle cx="66" cy="45" r="5" fill="#333"/>
  <circle cx="35" cy="43" r="1.5" fill="white"/><circle cx="67" cy="43" r="1.5" fill="white"/>"""

_ES = """<ellipse cx="34" cy="46" rx="6" ry="3.5" fill="white" stroke="#333" stroke-width="1.8"/>
  <ellipse cx="66" cy="46" rx="6" ry="3.5" fill="white" stroke="#333" stroke-width="1.8"/>
  <path d="M28 42 Q34 38 40 42" stroke="#333" stroke-width="2" fill="none"/>
  <path d="M60 42 Q66 38 72 42" stroke="#333" stroke-width="2" fill="none"/>
  <ellipse cx="34" cy="47" rx="3.5" ry="2" fill="#333"/>
  <ellipse cx="66" cy="47" rx="3.5" ry="2" fill="#333"/>"""

_EA = """<circle cx="34" cy="46" r="6" fill="white" stroke="#333" stroke-width="1.8"/>
  <circle cx="66" cy="46" r="6" fill="white" stroke="#333" stroke-width="1.8"/>
  <circle cx="34" cy="47" r="3" fill="#333"/><circle cx="66" cy="47" r="3" fill="#333"/>
  <line x1="27" y1="37" x2="41" y2="42" stroke="#333" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="73" y1="37" x2="59" y2="42" stroke="#333" stroke-width="2.5" stroke-linecap="round"/>"""

_EX = """<line x1="27" y1="38" x2="41" y2="52" stroke="#333" stroke-width="3" stroke-linecap="round"/>
  <line x1="41" y1="38" x2="27" y2="52" stroke="#333" stroke-width="3" stroke-linecap="round"/>
  <line x1="59" y1="38" x2="73" y2="52" stroke="#333" stroke-width="3" stroke-linecap="round"/>
  <line x1="73" y1="38" x2="59" y2="52" stroke="#333" stroke-width="3" stroke-linecap="round"/>"""

EMOTION_CARDS = [
    ("btn_happy",   "I feel happy", _svg("#FFE066","#333",_EO, '<path d="M32 60 Q50 74 68 60" stroke="#333" stroke-width="2.5" fill="#FF8A80" stroke-linecap="round"/>', '<circle cx="31" cy="58" r="5" fill="#FFAB91" opacity=".7"/><circle cx="69" cy="58" r="5" fill="#FFAB91" opacity=".7"/>', "Happy")),
    ("btn_sad",     "I feel sad", _svg("#90CAF9","#333",_EO, '<path d="M32 66 Q50 54 68 66" stroke="#333" stroke-width="2.5" fill="none" stroke-linecap="round"/>', '<line x1="37" y1="53" x2="35" y2="63" stroke="#5599cc" stroke-width="2" opacity=".8"/><line x1="63" y1="53" x2="65" y2="63" stroke="#5599cc" stroke-width="2" opacity=".8"/>', "Sad")),
    ("btn_angry",   "I feel angry", _svg("#EF9A9A","#333",_EA, '<path d="M32 66 Q50 56 68 66" stroke="#333" stroke-width="2.5" fill="none" stroke-linecap="round"/>', '<path d="M40 28 Q45 22 50 28 Q55 22 60 28" stroke="#c0392b" stroke-width="2" fill="none"/>', "Angry")),
    ("btn_scared",  "I feel scared", _svg("#CE93D8","#333",_EW, '<path d="M34 64 L39 58 L44 64 L49 58 L54 64 L59 58 L64 64" stroke="#333" stroke-width="2" fill="none" stroke-linecap="round"/>', "", "Scared")),
    ("btn_tired",   "I am tired", _svg("#A5D6A7","#333",_ES, '<path d="M35 64 Q50 70 65 64" stroke="#333" stroke-width="2" fill="none" stroke-linecap="round"/>', '<path d="M63 28 Q71 18 76 26" stroke="#aaa" stroke-width="1.5" fill="none"/>', "Tired")),
    ("btn_excited", "I feel excited", _svg("#FFF176","#333",_EO, '<ellipse cx="50" cy="63" rx="11" ry="7" fill="#FF8A80" stroke="#333" stroke-width="2"/>', '<circle cx="30" cy="57" r="5" fill="#FFAB91" opacity=".7"/><circle cx="70" cy="57" r="5" fill="#FFAB91" opacity=".7"/>', "Excited")),
    ("btn_hungry",  "I am hungry", _svg("#FFCC80","#333",_EO, '<path d="M34 63 Q50 73 66 63" stroke="#333" stroke-width="2.5" fill="#FF8A80" stroke-linecap="round"/>', '<text x="50" y="30" text-anchor="middle" font-size="13">🍕</text>', "Hungry")),
    ("btn_bathroom","Bathroom", _svg("#80DEEA","#333",_EO, '<path d="M37 63 Q50 70 63 63" stroke="#333" stroke-width="2" fill="none" stroke-linecap="round"/>', '<text x="50" y="30" text-anchor="middle" font-size="13">🚻</text>', "Bathroom")),
    ("btn_hurt",    "I am hurt", _svg("#FFCDD2","#333",_EX, '<path d="M34 66 Q50 58 66 66" stroke="#333" stroke-width="2.5" fill="none" stroke-linecap="round"/>', '<path d="M61 26 L66 18 L71 26 L66 22 Z" fill="#E53935"/>', "Hurt")),
    ("btn_yes",     "Yes", """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120" width="84" height="100"><circle cx="50" cy="50" r="36" fill="#A5D6A7" stroke="#2E7D32" stroke-width="3"/><polyline points="27,50 41,64 73,32" stroke="#2E7D32" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/><text x="50" y="108" text-anchor="middle" font-family="Arial Rounded MT Bold,Arial,sans-serif" font-size="12" font-weight="bold" fill="#222">Yes</text></svg>"""),
    ("btn_no",      "No", """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120" width="84" height="100"><circle cx="50" cy="50" r="36" fill="#FFCDD2" stroke="#C62828" stroke-width="3"/><line x1="30" y1="30" x2="70" y2="70" stroke="#C62828" stroke-width="7" stroke-linecap="round"/><line x1="70" y1="30" x2="30" y2="70" stroke="#C62828" stroke-width="7" stroke-linecap="round"/><text x="50" y="108" text-anchor="middle" font-family="Arial Rounded MT Bold,Arial,sans-serif" font-size="12" font-weight="bold" fill="#222">No</text></svg>"""),
]

# ---------------------------------------------------------------------------
# HTML PICTURE BOARD
# ---------------------------------------------------------------------------
CARD_CSS = """<style>
.aac-board{display:flex;flex-wrap:wrap;gap:10px;padding:6px 0;}
.aac-card{display:flex;flex-direction:column;align-items:center;background:#fff;border:3px solid #ddd;border-radius:14px;padding:6px 8px;cursor:pointer;user-select:none;transition:border-color .15s,box-shadow .15s,transform .1s;min-width:76px;}
.aac-card:hover{border-color:#42A5F5;box-shadow:0 4px 14px rgba(66,165,245,.35);transform:translateY(-2px);}
.aac-card:active,.aac-card.pressed{transform:scale(.95);border-color:#1565C0;background:#E3F2FD;}
</style>"""

def build_html_board(cards):
    items = "".join(f'<div class="aac-card" onclick="grClick(\'{eid}\', this)">{svg}</div>\n' for (eid, _, svg) in cards)
    return CARD_CSS + f'<div class="aac-board">{items}</div>'

HEAD_JS = """<script>
function grClick(eid, cardEl) {
    var wrapper = document.getElementById(eid);
    if (!wrapper) return;
    var btn = wrapper.querySelector('button');
    if (!btn) btn = (wrapper.tagName === 'BUTTON') ? wrapper : null;
    if (btn) btn.click();
    if (cardEl) { cardEl.classList.add('pressed'); setTimeout(() => cardEl.classList.remove('pressed'), 300); }
}
</script>"""

HIDDEN_BTN_CSS = "\n".join(f"#{eid} {{ position:absolute !important; width:1px !important; height:1px !important; padding:0 !important; margin:-1px !important; overflow:hidden !important; clip:rect(0,0,0,0) !important; white-space:nowrap !important; border:0 !important; }}" for (eid, _, __) in EMOTION_CARDS)

# ---------------------------------------------------------------------------
# RAG ENGINE
# ---------------------------------------------------------------------------
_STOPWORDS = {"i","me","my","we","you","he","she","it","they","a","an","the","is","am","are","was","were","be","been","being","have","has","had","do","does","did","will","would","shall","should","may","might","can","could","to","of","in","on","at","for","with","and","or","but","not","so","if","this","that","these","those","from","by","as","up","out","about","into","than","then","when","where","what","how","feel","just","very","also","your"}

class RAGEngine:
    CHUNK_SIZE, CHUNK_OVERLAP, TOP_K = 120, 30, 1
    def __init__(self): self.chunks, self.tf_idf, self.idf, self.doc_name, self.loaded = [], [], {}, "", False
    def load_text(self, raw_text: str, doc_name: str = "document") -> str:
        if not raw_text.strip(): return "⚠️ Empty."
        words = raw_text.split()
        self.chunks = [" ".join(words[i : i + self.CHUNK_SIZE]) for i in range(0, len(words), max(1, self.CHUNK_SIZE - self.CHUNK_OVERLAP))]
        self.doc_name, self.loaded = doc_name, True
        self._build_index()
        return f"✅ Loaded {doc_name}."
    def load_file(self, filepath: str) -> str:
        if not os.path.exists(filepath): return "⚠️ Not found."
        ext, name = os.path.splitext(filepath)[1].lower(), os.path.basename(filepath)
        try:
            if ext == ".txt":
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f: raw = f.read()
            elif ext == ".pdf":
                import PyPDF2
                with open(filepath, "rb") as f: raw = "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(f).pages)
            else: return "⚠️ Unsup ext."
            return self.load_text(raw, doc_name=name)
        except Exception as e: return f"⚠️ Error: {e}"
    def clear(self): self.chunks, self.tf_idf, self.idf, self.doc_name, self.loaded = [], [], {}, "", False
    def _tokenise(self, text: str): return [t for t in re.findall(r"[a-z]+", text.lower()) if t not in _STOPWORDS and len(t) > 2]
    def _build_index(self):
        N = len(self.chunks)
        tf_list = [Counter(self._tokenise(c)) for c in self.chunks]
        df = Counter(); [df.update(set(tf.keys())) for tf in tf_list]
        self.idf = {t: math.log((N+1)/(c+1))+1 for t, c in df.items()}
        self.tf_idf = [{t: (v/max(len(self._tokenise(self.chunks[i])),1)) * self.idf.get(t,1.0) for t, v in tf.items()} for i, tf in enumerate(tf_list)]
    def retrieve(self, query: str):
        if not self.loaded or not self.chunks: return None
        q = self._tokenise(query)
        if not q: return None
        scores = [sum(cw.get(t, 0.0) for t in q) for cw in self.tf_idf]
        best = max(range(len(scores)), key=lambda i: scores[i])
        return self.chunks[best] if scores[best] > 0.01 else None

BUILTIN_KNOWLEDGE = """EMOTIONAL RULES: If sad validate & suggest hug. If angry short sentences & calm space. If scared reassure & say 'I am here'. If excited match energy & share. SOCIAL: Praise greets, manners & questions."""
rag = RAGEngine(); rag.load_text(BUILTIN_KNOWLEDGE, "built-in")

class Session:
    def __init__(self): self.scenario, self.preferences, self.state_log, self.last_responses, self.history, self.turn_count, self.scenario_just_switched, self.completed_tasks = "parent", {}, [], [], [], 0, False, []
    def reset(self): self.__init__(); return [], "🌟 Ready!", None
    def switch_scenario(self, s): self.scenario, self.scenario_just_switched = s, True; return SCENARIO_PROFILES[s]["greeting"]
    def update_memory(self, t):
        t = t.lower()
        if "i like" in t: self.preferences["pref"] = t.split("i like", 1)[-1].strip()
        state = "crisis" if any(w in t for w in ["help","panic","hurt"]) else "emotional" if any(w in t for w in ["sad","happy","mad"]) else "functional" if any(w in t for w in ["hungry","bathroom","tired"]) else "social"
        self.state_log.append(state); self.turn_count += 1; return state
    def detect_pattern(self): return f"Pattern: {Counter(self.state_log).most_common(1)[0][0]}" if len(self.state_log) >= 3 else ""
    def register_response(self, t): self.last_responses.append(t[:80]); self.last_responses = self.last_responses[-3:]

session = Session()

def handle_interaction(text, history):
    if not text.strip(): return history, "😊 Ready", None
    state = session.update_memory(text)
    prompt = f"Role: {SCENARIO_PROFILES[session.scenario]['role']}. Strategy: {STRATEGY_KB.get(state)}. {session.detect_pattern()}. Doc: {rag.retrieve(text)}"
    try:
        res = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role":"system","content":prompt}] + [{"role":m["role"],"content":m["content"]} for m in history[-10:]] + [{"role":"user","content":text}], max_tokens=100)
        ai = res.choices[0].message.content.strip()
    except: ai = "I'm here."
    session.register_response(ai); audio = generate_speech(ai)
    return history + [{"role":"user","content":text}, {"role":"assistant","content":ai}], build_coaching_label(text, state, None), audio

def generate_speech(text):
    if not text: return None
    fname = f"voice_{int(time.time()*1000)}.mp3"
    try: gTTS(text=text[:500], lang='en').save(fname); return fname
    except: return None

def process_audio(audio, history):
    if not audio: return history, "🎙️ No audio", None, audio
    try: text = stt_model.transcribe(audio)["text"].strip()
    except: return history, "🎙️ Error hearing", None, audio
    if not text: return history, "🎙️ Empty", None, audio
    h, l, a = handle_interaction(text, history)
    return h, l, a, None

def task_completed(name, checked, history):
    if not checked: return history, "😊 Ready", None
    ai = f"Great job finishing {name}!"
    return history + [{"role":"user","content":f"I finished {name}"}, {"role":"assistant","content":ai}], f"🌟 Done: {name}", generate_speech(ai)

with gr.Blocks() as demo:
    gr.Markdown("# 🧠 AutiSense AI")
    with gr.Row():
        mode_p, mode_t, mode_c = gr.Button("🏠 Parent"), gr.Button("🏫 Teacher"), gr.Button("🤝 Caretaker")
    with gr.Row():
        with gr.Column(scale=3):
            chat = gr.Chatbot(height=320)
            gr.HTML(build_html_board(EMOTION_CARDS))
            hidden_btns = [gr.Button(t, elem_id=e) for (e, t, _) in EMOTION_CARDS]
            mic = gr.Audio(sources=["microphone"], type="filepath", label="🎙️ Speak")
            with gr.Row():
                send_btn, audio_out = gr.Button("📤 Send", variant="primary"), gr.Audio(autoplay=True, visible=True)
        with gr.Column(scale=2):
            label = gr.Label(value="🌟 Ready!")
            tasks = [gr.Checkbox(label=t) for t in DAILY_TASKS]
            doc = gr.File(label="Upload Guide", file_types=[".txt", ".pdf"], type="filepath")
            reset = gr.Button("🔄 Start Fresh")

    for i, hb in enumerate(hidden_btns): hb.click(lambda h, t=EMOTION_CARDS[i][1]: handle_interaction(t, h), [chat], [chat, label, audio_out])
    mode_p.click(lambda: session.switch_scenario("parent"), None, label)
    mode_t.click(lambda: session.switch_scenario("teacher"), None, label)
    mode_c.click(lambda: session.switch_scenario("caretaker"), None, label)
    send_btn.click(process_audio, [mic, chat], [chat, label, audio_out, mic])
    for i, cb in enumerate(tasks): cb.change(lambda c, h, n=DAILY_TASKS[i]: task_completed(n, c, h), [cb, chat], [chat, label, audio_out])
    doc.change(lambda f, l: (rag.load_file(f.name) if f else "Built-in only"), [doc, label], [label])
    reset.click(session.reset, None, [chat, label, audio_out])

demo.launch(head=HEAD_JS, css=HIDDEN_BTN_CSS + ".aac-section-label{font-size:15px;font-weight:700;color:#555;}")
