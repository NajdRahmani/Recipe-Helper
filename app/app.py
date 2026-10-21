"""Recipe Helper v4 - Web UI (Streamlit). Run: streamlit run app.py"""
import base64
import json

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="Recipe Helper", page_icon="🍳", layout="wide")

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("⚙️ Settings")
    webhook_url = st.text_input(
        "n8n webhook URL", value="http://localhost:5678/webhook/recipe-helper"
    )

    st.divider()
    st.subheader("🎛️ Filters (optional)")

    max_minutes = st.slider("Max time (min)", 0, 240, 240, step=10)
    max_kcal = st.slider("Max calories / serving", 0, 2000, 2000, step=50)
    min_protein = st.slider("Min protein (g)", 0, 60, 0, step=5)
    vegetarian = st.checkbox("Vegetarian only")

    st.divider()
    if st.button("♻️ Clear results"):
        st.session_state.clear()

# ------------------------------------------------------------------ inputs
st.title("🍳 Recipe Helper")
col1, col2 = st.columns([3, 2])

with col1:
    query = st.text_area(
        "What do you have / what do you feel like?",
        placeholder="e.g. I have rice, eggs and soy sauce — something quick?",
        height=100,
    )

with col2:
    image_file = st.file_uploader(
        "📸 Or upload a fridge photo (optional)",
        type=["png", "jpg", "jpeg"],
    )
    if image_file:
        st.image(image_file, width=200)

# ------------------------------------------------------------------ build request
def build_payload():
    filters = {
        "max_minutes": max_minutes if max_minutes < 240 else None,
        "max_kcal": max_kcal if max_kcal < 2000 else None,
        "min_protein_g": min_protein if min_protein > 0 else None,
        "vegetarian": True if vegetarian else None,
    }
    filters = {k: v for k, v in filters.items() if v is not None}

    image_b64 = None
    if image_file:
        image_b64 = base64.b64encode(image_file.getvalue()).decode()

    return {"query": query, "image_b64": image_b64, "filters": filters}


if st.button("🍳 Find recipes", type="primary", use_container_width=True):
    if not query and not image_file:
        st.warning("Type something or upload a photo first.")
    else:
        with st.spinner("🤔 Parsing, searching, cooking up an answer..."):
            try:
                r = requests.post(webhook_url, json=build_payload(), timeout=120)
                r.raise_for_status()
                st.session_state["result"] = r.json()
            except requests.RequestException as e:
                st.error(f"Backend error: {e}")

# ------------------------------------------------------------------ display
result = st.session_state.get("result")
if result:
    st.divider()
    if result.get("error"):
        st.error(result["error"])
    else:
        # header card
        c1, c2, c3 = st.columns(3)
        c1.metric("⏱️ Time", f"{result.get('minutes', '?')} min")
        c2.metric("🔥 Calories", f"{result.get('kcal', '?')} kcal")
        c3.metric("🥩 Protein", f"{result.get('protein_g', '?')} g")

        if result.get("vegetarian"):
            st.badge("🥬 Vegetarian")
        if result.get("image_url"):
            st.image(result["image_url"], width=400)

        st.subheader(f"🍽️ {result.get('name', 'Recipe')}")

        left, right = st.columns(2)
        with left:
            st.markdown("### 🛒 Ingredients")
            for ing in result.get("ingredients", []):
                st.markdown(f"- {ing}")
        with right:
            st.markdown("### 👨‍🍳 Steps")
            for i, step in enumerate(result.get("steps", []), 1):
                st.markdown(f"**{i}.** {step}")

        # nutrition table
        st.markdown("### 📊 Nutrition per serving")
        st.dataframe(
            pd.DataFrame([{
                "Calories (kcal)": result.get("kcal"),
                "Protein (g)": result.get("protein_g"),
                "Carbs (g)": result.get("carbs_g"),
                "Fat (g)": result.get("fat_g"),
            }]),
            use_container_width=True, hide_index=True,
        )

        if result.get("chef_note"):
            st.info(f"💬 **Chef's note:** {result['chef_note']}")