import streamlit as st

st.set_page_config(page_title="SmartCampus", page_icon="🎓")

st.title("SmartCampus")
st.caption("L'assistant de la vie universitaire — Toulouse Capitole")

chat, edt, actus = st.tabs(["Chat", "Mon emploi du temps", "Actualités"])

with chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        st.chat_message(message["role"]).write(message["content"])

    question = st.chat_input("Pose ta question")
    if question:
        reponse = "Bonjour ! Je ne sais pas encore répondre : le chatbot arrive bientôt."
        st.session_state.messages.append({"role": "user", "content": question})
        st.session_state.messages.append({"role": "assistant", "content": reponse})
        st.rerun()

with edt:
    st.info("Bientôt : les cours de la semaine pour ton groupe, et les salles libres sur un créneau.")

with actus:
    st.info("Bientôt : les annonces de l'université, résumées en trois lignes et rangées par catégorie.")
