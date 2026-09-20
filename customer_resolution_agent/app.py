import streamlit as st
from datetime import datetime
from data import CUSTOMERS, POLICY, EXERCISE_DATE
from agent import resolve

st.set_page_config(page_title="AIONOS Resolution Agent", page_icon="✈️", layout="wide")

# ----------------------------------------------------------------------------
# Palette — light lavender, pink→cream, cream, and blue pastels
# ----------------------------------------------------------------------------
BG_LAVENDER = "#C7B4EE"
CARD_FOCUS_GRADIENT = "linear-gradient(135deg, #F6BFC9 0%, #F7E9C9 100%)"
PINK = "#F2A6BB"
PINK_SOFT = "#FBDEE6"
CREAM = "#F5E9C6"
CREAM_SOFT = "#FBF3DE"
BLUE = "#A9D5F2"
BLUE_SOFT = "#DCEEFB"
WHITE = "#FFFFFF"
TEXT_DARK = "#3B2C55"
TEXT_MUTED = "#6B5B87"

st.markdown("""
<style>
.stApp { background: #C7B4EE; }
section[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid #E4D9F7;
}
section[data-testid="stSidebar"] * { color: #3B2C55; }

#MainMenu, footer {visibility: hidden;}
.block-container { padding-top: 1.6rem; max-width: 1100px; }

h1, h2, h3 { color: #3B2C55 !important; font-weight: 800 !important; }
p, span, label, .stMarkdown { color: #3B2C55; }
[data-testid="stCaptionContainer"] { color: #6B5B87 !important; }

/* Metrics */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #F6BFC9 0%, #F7E9C9 100%);
    border-radius: 16px;
    padding: 14px 16px;
}
[data-testid="stMetricLabel"] { color: #6B5B87 !important; }
[data-testid="stMetricValue"] { color: #3B2C55 !important; font-weight: 800 !important; }

/* Buttons */
.stButton > button {
    background: #FFFFFF;
    color: #3B2C55;
    border: 1.5px solid #E4D9F7;
    border-radius: 999px;
    font-weight: 700;
    padding: 6px 18px;
}
.stButton > button:hover {
    background: #FBDEE6;
    border-color: #F2A6BB;
    color: #3B2C55;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] {
    background: #FFFFFF;
    border-radius: 999px;
    color: #6B5B87;
    padding: 6px 16px;
    font-weight: 700;
}
.stTabs [aria-selected="true"] {
    background: #F2A6BB !important;
    color: #3B2C55 !important;
}

/* Expander */
[data-testid="stExpander"] {
    background: #FBF3DE;
    border: 1px solid #F0E4BE;
    border-radius: 14px;
}
[data-testid="stExpander"] summary { color: #3B2C55; font-weight: 700; }

/* Chat bubbles */
[data-testid="stChatMessage"] {
    border-radius: 16px;
    padding: 4px 8px;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: #FBDEE6;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: #DCEEFB;
}

/* Code block (example prompt) */
.stCodeBlock, pre { border-radius: 14px !important; }

/* Divider */
hr { border-color: #E4D9F7 !important; }

.info-card {
    border-radius: 16px; padding: 14px 18px; font-size: 0.9rem;
    color: #3B2C55; margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)


def init():
    for k, v in {"messages": [], "action_log": [], "active_customer": list(CUSTOMERS)[0]}.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset(customer):
    st.session_state.messages = []
    st.session_state.action_log = []
    st.session_state.active_customer = customer


def log(role, detail):
    st.session_state.action_log.append({"time": datetime.now().strftime("%H:%M:%S"), "role": role, "detail": detail})


init()

st.title("✈️ Customer-Facing Resolution Agent")
st.caption(f"Airline disruption prototype • Exercise date: {EXERCISE_DATE} • Policy-grounded demo")

with st.sidebar:
    st.header("Demo customer")
    names = list(CUSTOMERS)
    selected = st.selectbox("Select customer", names, index=names.index(st.session_state.active_customer))
    if selected != st.session_state.active_customer:
        reset(selected)
        st.rerun()
    c = CUSTOMERS[selected]
    st.metric("Loyalty tier", c["tier"])
    st.write(f"**PNR:** {c['pnr']}")
    st.write(f"**Contact:** {c['contact']}")
    st.write(f"**Travel history:** {c['history']}")
    if st.button("Reset conversation", use_container_width=True):
        reset(selected)
        st.rerun()
    st.divider()
    st.subheader("Guardrails")
    st.markdown(
        '<div class="info-card" style="background:#F5E9C6;">Uses only supplied exercise data. '
        'It does not invent seat availability, prices, refund destinations, or extra compensation.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Policy reference"):
        for v in POLICY.values():
            st.write("•", v)

conversation, actions, booking = st.tabs(["Conversation", "Action record", "Booking & policy"])
with conversation:
    if not st.session_state.messages:
        st.info("Try the assignment scenario or an edge case such as a legal threat or alternate refund method.")
        examples = {
            "Priya Nair": "I'm furious. I want a full cash refund plus a free business-class upgrade on my return.",
            "Arvind Kulkarni": "This delay is frustrating. I want a hotel because I'm missing my meeting.",
            "Meher Kaur": "I want a full-night hotel and a different higher-fare flight. The fare difference is ₹2,000.",
        }
        st.code(examples[selected], language=None)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    prompt = st.chat_input("Type the customer's message")
    if prompt is not None and prompt.strip():
        st.session_state.messages.append({"role": "user", "content": prompt})
        log("Customer", prompt)
        result = resolve(selected, prompt)
        st.session_state.messages.append({"role": "assistant", "content": result.message})
        log("Agent", result.message)
        for a in result.actions:
            log("Action", f"{a.action_type} — {a.status}: {a.detail}")
        if result.escalation:
            log("Escalation", result.escalation)
        st.rerun()

with actions:
    st.subheader("Auditable conversation & action trail")
    if not st.session_state.action_log:
        st.info("No actions recorded yet.")
    for item in st.session_state.action_log:
        st.write(f"**{item['time']} · {item['role']}**")
        st.write(item["detail"])
        st.divider()

with booking:
    st.subheader("Customer booking")
    st.write({"customer": selected, "tier": c["tier"], "pnr": c["pnr"]})
    for no, f in c["flights"].items():
        with st.expander(f"{no} · {f['route']} · {f['status_display']}", expanded=True):
            st.json(f)
    st.subheader("Decision policy")
    for k, v in POLICY.items():
        st.write(f"**{k.replace('_', ' ').title()}:** {v}")
st.divider()
st.caption("Actions are simulated/recorded locally because the assignment provides no live airline booking, payment, CRM, inventory, voucher, lounge, or hotel API.")