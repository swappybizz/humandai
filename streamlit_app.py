import streamlit as st
import uuid
import random
from st_paywall import add_auth
from pymongo import MongoClient, TEXT
from bson.regex import Regex
from fuzzysearch import find_near_matches

st.set_page_config(page_title="ExpertAI", page_icon=":rocket:", layout="wide")
if 'session_id' not in st.session_state:
    st.session_state.session_id = f"ST_ASSTT_{str(uuid.uuid4())}"

if "selected_detail_expert" not in st.session_state:
    st.session_state.selected_detail_expert = None


# Dummy expert data
experts = [
    {
        "Expert name": "John Doe",
        "Expert description": "Expert in compliance and risk management",
        "subsribers": 140,
        "rating": "⭐⭐⭐⭐⚫"
    },
    {
        "Expert name": "Jane Smith",
        "Expert description": "Specialist in data privacy and compliance",
        "subsribers": 203,
        "rating": "⭐⭐⭐⭐⭐"
    },
    {
        "Expert name": "Alice Johnson",
        "Expert description": "Expert in financial compliance and auditing",
        "subsribers": 230,
        "rating": "⭐⭐⭐⚫⚫"
    },
    {
        "Expert name": "Bob Brown",
        "Expert description": "Specialist in cybersecurity compliance",
        "subsribers": 450,
        "rating": "⭐⭐⚫⚫⚫"
    },
    {
        "Expert name": "Carol White",
        "Expert description": "Compliance expert with a focus on healthcare regulations",
        "subsribers": 50,
        "rating": "⭐⭐⭐⭐⭐"
    }
]

# Add authentication
add_auth(required=True)
with st.sidebar:
    st.write(f"Subscription status: {'Subscribed' if st.session_state.user_subscribed else 'Not subscribed'}")
    st.write(f"{st.session_state.email}")

MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client['ExpertAI']
client_collection = db['expertai_client']
expert_collection = db['expertai_expert']
chat_collection = db['expertai_chat']  # Collection for chat history
chat_archiver = db['expertai_chat_archive']  # Collection for chat history
# Create text index on 'Expert description' and 'Expert name' if not exists
expert_collection.create_index([("Expert name", TEXT), ("Expert description", TEXT)])

# Insert dummy data if it doesn't already exist
for expert in experts:
    if not expert_collection.find_one({"Expert name": expert["Expert name"]}):
        expert_collection.insert_one(expert)

def fuzzy_search(query, experts):
    matches = []
    for expert in experts:
        name = expert["Expert name"]
        description = expert["Expert description"]
        if (find_near_matches(query, name, max_l_dist=2) or
                find_near_matches(query, description, max_l_dist=2)):
            matches.append(expert)
    return matches

def search_experts(query):
    if query:
        # Text search
        regex_query = Regex(query, 'i')  # Case-insensitive search
        text_search_results = list(expert_collection.find(
            {"$text": {"$search": query}}
        ))
        # Fuzzy search on name and description
        fuzzy_search_results = fuzzy_search(query, text_search_results)
        return fuzzy_search_results
    return []

def is_hired(user_email, expert_name):
    user_data = client_collection.find_one({"email": user_email})
    if user_data and "selected_experts" in user_data:
        return expert_name in user_data["selected_experts"]
    return False

def update_hired_status(user_email, expert_name, hired):
    user_data = client_collection.find_one({"email": user_email})
    if user_data:
        if "selected_experts" not in user_data:
            user_data["selected_experts"] = []
        if hired:
            if expert_name not in user_data["selected_experts"]:
                user_data["selected_experts"].append(expert_name)
        else:
            if expert_name in user_data["selected_experts"]:
                user_data["selected_experts"].remove(expert_name)
        client_collection.update_one({"email": user_email}, {"$set": {"selected_experts": user_data["selected_experts"]}})
    else:
        client_collection.insert_one({"email": user_email, "selected_experts": [expert_name] if hired else []})

def get_chat_history(user_email, expert_name):
    chat_history = chat_collection.find_one({"user_email": user_email, "expert_name": expert_name})
    if chat_history and "messages" in chat_history:
        return chat_history["messages"]
    return []

def save_chat_message(user_email, expert_name, role, message):
    chat_history = chat_collection.find_one({"user_email": user_email, "expert_name": expert_name})
    if not chat_history:
        chat_history = {"user_email": user_email, "expert_name": expert_name, "messages": []}
    chat_history["messages"].append({"role": role, "message": message})
    chat_collection.update_one({"user_email": user_email, "expert_name": expert_name}, {"$set": chat_history}, upsert=True)

def save_to_archive(user_email, expert_name, chat_history):
    archive_collection = db['expertai_chat_archive']
    archive_collection.insert_one({"user_email": user_email,
                                   "expert_name": expert_name,
                                   "messages": chat_history,
                                   "session_id": st.session_state.session_id})
@st.experimental_fragment
def render_chat(expert_name):
    user_email = st.session_state.email
    chat_history = get_chat_history(user_email, expert_name)
    if st.button("➕ knowlege & new chat", key=f"{expert_name}_new_chat_",use_container_width=True):
        st.session_state.pop(f"{expert_name}_chat_input", None)
        save_to_archive(user_email, expert_name, chat_history)
        chat_collection.delete_one({"user_email": st.session_state.email, "expert_name": expert_name})
        st.rerun()
    for msg in chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["message"])
    if prompt := st.chat_input(f"{expert_name} & Bot are here to help you, lets begin", key=f"{expert_name}_chat_input"):
        response = "This is a simulated response."  # Replace with actual AI response generation
        save_chat_message(user_email, expert_name, "user", prompt)
        save_chat_message(user_email, expert_name, "ai", response)
        st.rerun()


tab1, tab2, tab3 = st.tabs(["Experts", "Knowledge Base", "Detailed Chat"])


# Add a search bar

with tab1:
    with st.container():
        query = st.text_input("Look up Your AI-Human Expert Duo", placeholder="Type Here")
        if query:
            experts_found = search_experts(query)
            if experts_found:
                st.write(f"Found {len(experts_found)} expert(s):")
                num_columns = 3
                columns = st.columns(num_columns)
                for idx, expert in enumerate(experts_found):
                    with columns[idx % num_columns]:
                        with st.container(border=True):
                            col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
                            with col1:
                                online_status = random.choice(["🟢", "⚫"])
                                st.write(f"##### {expert['Expert name']}{online_status}")
                            with col2:
                                st.write(f"**Subs:** {expert['subsribers']}")
                            with col3:
                                st.write(f"{expert['rating']}")
                            with col4:
                                hired = is_hired(st.session_state.email, expert['Expert name'])
                                heart = "❤️" if hired else "🖤"
                                checkbox = st.checkbox(f"{heart}", value=hired, key=f"{expert['Expert name']}_{idx}")
                                if checkbox != hired:
                                    update_hired_status(st.session_state.email, expert['Expert name'], checkbox)

                            st.write(f"{expert['Expert description']}")
                            if st.button("New Chat", key=f"{expert['Expert name']}_new_chat",use_container_width=True):
                                    # 'delete from session and db'
                                    st.session_state.pop(f"{expert['Expert name']}_chat_input", None)
                                    chat_collection.delete_one({"user_email": st.session_state.email, "expert_name": expert['Expert name']})
                                    
                            with st.expander(f"Chat {expert['Expert name']} | 🤖"):
                                render_chat(expert['Expert name'])
            else:
                st.write("No experts found matching the query.")
