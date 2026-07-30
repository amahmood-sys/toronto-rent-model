"""
Toronto Rental Predictor — Streamlit app.

Predicts monthly rent from listing features using an XGBoost model trained on
real Kijiji listings. Inference runs on the exported model JSON
(model/model_export.json) via a pure-Python tree traversal, so no joblib /
scikit-learn / xgboost version matching is required to deploy.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

MODEL_PATH = Path(__file__).parent / "model" / "model_export.json"

# Feature order after sklearn ColumnTransformer(remainder='passthrough'):
#   OrdinalEncoder outputs first: f0=neighbourhood, f1=property_type
#   then passthrough: f2=bedrooms, f3=bathrooms, f4=size_sqft,
#   f5=has_parking, f6=has_laundry, f7=furnished, f8=pets_allowed


@st.cache_resource
def load_model():
    """Load the exported model and pre-build a nodeid->node map per tree."""
    model = json.loads(MODEL_PATH.read_text())

    def build_map(node, out):
        out[node["nodeid"]] = node
        for child in node.get("children", []):
            build_map(child, out)
        return out

    maps = [build_map(root, {}) for root in model["trees"]]
    return model, maps


def _traverse(node, node_map, features):
    while "leaf" not in node:
        fi = int(node["split"][1:])
        v = features[fi]
        if v is None:
            nxt = node["missing"]
        elif v < node["split_condition"]:
            nxt = node["yes"]
        else:
            nxt = node["no"]
        node = node_map[nxt]
    return node["leaf"]


def predict(model, maps, inp):
    cats = model["categories"]
    nh = cats["neighbourhood"].index(inp["neighbourhood"]) \
        if inp["neighbourhood"] in cats["neighbourhood"] else -1
    pt = cats["property_type"].index(inp["property_type"]) \
        if inp["property_type"] in cats["property_type"] else -1

    features = [
        nh,                              # f0 neighbourhood
        pt,                              # f1 property_type
        inp["bedrooms"],                 # f2
        inp["bathrooms"],                # f3
        inp["size_sqft"],                # f4
        1 if inp["has_parking"] else 0,  # f5
        1 if inp["has_laundry"] else 0,  # f6
        1 if inp["furnished"] else 0,    # f7
        1 if inp["pets_allowed"] else 0, # f8
    ]

    total = model["base_score"]
    for root, node_map in zip(model["trees"], maps):
        total += _traverse(root, node_map, features)
    return round(total)


# ----------------------------------------------------------------------------
st.set_page_config(page_title="Toronto Rental Predictor", page_icon="🏙️",
                   layout="centered")

model, maps = load_model()
neighbourhoods = sorted(model["categories"]["neighbourhood"])
property_types = model["categories"]["property_type"]

st.title("🏙️ Toronto Rental Predictor")
st.caption(
    "Estimated monthly rent from an XGBoost model trained on real Kijiji "
    "listings. Adjust the features and see the predicted price update."
)

with st.sidebar:
    st.header("Listing features")
    _default_nb = "Bay Street Corridor"
    neighbourhood = st.selectbox("Neighbourhood", neighbourhoods,
                                 index=neighbourhoods.index(_default_nb)
                                 if _default_nb in neighbourhoods else 0)
    property_type = st.selectbox("Property type", property_types,
                                 index=property_types.index("Condo")
                                 if "Condo" in property_types else 0)
    bedrooms = st.slider("Bedrooms", 0, 5, 2)
    bathrooms = st.slider("Bathrooms", 1, 4, 1)
    size_sqft = st.slider("Size (sq ft)", 300, 2500, 750, step=25)

    st.subheader("Amenities")
    c1, c2 = st.columns(2)
    with c1:
        has_parking = st.checkbox("Parking", value=True)
        furnished = st.checkbox("Furnished", value=False)
    with c2:
        has_laundry = st.checkbox("In-suite laundry", value=True)
        pets_allowed = st.checkbox("Pets allowed", value=False)

inp = dict(neighbourhood=neighbourhood, property_type=property_type,
           bedrooms=bedrooms, bathrooms=bathrooms, size_sqft=size_sqft,
           has_parking=has_parking, has_laundry=has_laundry,
           furnished=furnished, pets_allowed=pets_allowed)

rent = predict(model, maps, inp)

st.metric(label=f"Estimated rent — {bedrooms}BR {property_type} in {neighbourhood}",
          value=f"${rent:,}/mo")

st.divider()

# How this listing compares across neighbourhoods (same config, all areas).
st.subheader("How this listing would price across Toronto")
st.caption("Same unit and amenities, predicted for every neighbourhood in the model.")

rows = []
for nb in model["categories"]["neighbourhood"]:
    r = predict(model, maps, {**inp, "neighbourhood": nb})
    rows.append({"Neighbourhood": nb, "Predicted rent": r})

df = pd.DataFrame(rows).set_index("Neighbourhood").sort_values(
    "Predicted rent", ascending=False)
st.bar_chart(df, horizontal=True, height=600)

st.divider()
st.caption(
    "Model: XGBoost (400 trees) · trained on scraped Kijiji listings · "
    "inference runs in pure Python on the exported model JSON."
)
