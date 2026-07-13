# app.py — Austin Airbnb Explorer | Streamlit + Altair Dashboard

# Import libraries
import streamlit as st
import altair as alt
import pandas as pd

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Austin Airbnb Explorer",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Data loading and cleaning ─────────────────────────────────────────────────

@st.cache_data
def load_data() -> pd.DataFrame:
    # Read the compressed CSV from the repo root directory
    df = pd.read_csv("listings.csv.gz", compression="gzip")
    ## Strip dollar signs and commas from PRICE
    df["price"] = df["price"].replace(r"[\$,]", "", regex=True).astype(float)
    ## Drop rows missing any key field used in the dashboard
    df = df.dropna(subset=[
        "price", "review_scores_rating", "latitude",
        "longitude", "room_type", "neighbourhood_cleansed", "accommodates"
    ])
    ## Remove extreme price outliers (above 95th percentile)
    df = df[df["price"] < df["price"].quantile(0.95)]
    return df

df = load_data()

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.title("Filter Listings")

# Room type multiselect — default to all types selected
all_room_types = sorted(df["room_type"].unique().tolist())
selected_rooms = st.sidebar.multiselect(
    "Room Type",
    options=all_room_types,
    default=all_room_types
)

# Price range slider — capped at 95th percentile for usability
min_p = int(df["price"].min())
max_p = int(df["price"].max())
price_range = st.sidebar.slider(
    "Price Range ($/night)",
    min_value=min_p,
    max_value=max_p,
    value=(min_p, 300)
)

# Neighborhood dropdown — top 15 ZIP codes by listing count
top_hoods = df["neighbourhood_cleansed"].value_counts().head(15).index.tolist()
hood_options = ["All Neighborhoods"] + top_hoods
selected_hood = st.sidebar.selectbox("Neighborhood (ZIP Code)", hood_options)

# Accommodates slider
max_acc = int(df["accommodates"].max())
acc_range = st.sidebar.slider(
    "Accommodates (guests)",
    min_value=1,
    max_value=max_acc,
    value=(1, max_acc)
)

# ── Apply all sidebar filters to the dataframe ────────────────────────────────
filtered = df[
    (df["room_type"].isin(selected_rooms)) &
    (df["price"] >= price_range[0]) &
    (df["price"] <= price_range[1]) &
    (df["accommodates"] >= acc_range[0]) &
    (df["accommodates"] <= acc_range[1])
]
if selected_hood != "All Neighborhoods":
    filtered = filtered[filtered["neighbourhood_cleansed"] == selected_hood]

# ── Dashboard title and listing count ────────────────────────────────────────
st.title("Austin Airbnb Explorer")
st.markdown(
    f"Showing **{len(filtered):,}** of **{len(df):,}** listings based on current filters."
)

# ── Metric summary row ────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Median Price/Night", f"${filtered['price'].median():.0f}" if len(filtered) else "N/A")
col2.metric("Avg Review Score", f"{filtered['review_scores_rating'].mean():.2f} / 5" if len(filtered) else "N/A")
col3.metric("Total Listings", f"{len(filtered):,}")
col4.metric("Avg Guests Hosted", f"{filtered['accommodates'].mean():.1f}" if len(filtered) else "N/A")

st.divider()

# ── CHART 1: Geographic map ───────────────────────────────────────────────────
st.subheader("Geographic Distribution of Listings")

# Sample for rendering performance on large filtered sets
sample_map = (
    filtered.sample(min(3000, len(filtered)), random_state=42)
    if len(filtered) > 3000 else filtered
)

# Plot latitude and longitude as x/y coordinates, colored by ROOM_TYPE
map_chart = (
    alt.Chart(sample_map)
    .mark_circle(opacity=0.45, size=20)
    .encode(
        x=alt.X("longitude:Q", scale=alt.Scale(zero=False), title="Longitude"),
        y=alt.Y("latitude:Q", scale=alt.Scale(zero=False), title="Latitude"),
        color=alt.Color(
            "room_type:N",
            scale=alt.Scale(scheme="tableau10"),
            legend=alt.Legend(title="Room Type")
        ),
        size=alt.Size(
            "price:Q",
            scale=alt.Scale(range=[15, 120]),
            legend=alt.Legend(title="Price ($/night)")
        ),
        tooltip=[
            alt.Tooltip("name:N", title="Listing"),
            alt.Tooltip("neighbourhood_cleansed:N", title="ZIP Code"),
            alt.Tooltip("price:Q", format="$.0f", title="Price/Night"),
            alt.Tooltip("review_scores_rating:Q", format=".2f", title="Rating"),
            alt.Tooltip("room_type:N", title="Room Type"),
            alt.Tooltip("accommodates:Q", title="Guests")
        ]
    )
    .properties(
        width=800,
        height=380,
        title="Austin Airbnb Listings — Sized by Price, Colored by Room Type"
    )
)

# Display the geographic map
st.altair_chart(map_chart, use_container_width=True)

st.divider()

# ── CHARTS 2 & 3: Linked brushing (price vs. rating → neighborhood bar) ───────
st.subheader("Price vs. Review Score — Linked to Neighborhood Breakdown")
st.caption(
    "Click and drag on the scatter plot to select listings by price and rating. "
    "The bar chart will update automatically to show median prices for selected listings."
)

# Sample for performance
sample_linked = (
    filtered.sample(min(2000, len(filtered)), random_state=42)
    if len(filtered) > 2000 else filtered
)

# Define a 2D interval brush selection on the scatter axes
brush = alt.selection_interval(encodings=["x", "y"])

# Chart 2a: Price vs. review score scatter — source of the brush
scatter = (
    alt.Chart(sample_linked)
    .mark_circle(opacity=0.5, size=45)
    .encode(
        x=alt.X(
            "review_scores_rating:Q",
            scale=alt.Scale(domain=[1, 5]),
            title="Review Score (out of 5)"
        ),
        y=alt.Y("price:Q", title="Price ($/night)"),
        color=alt.condition(
            brush,
            alt.Color(
                "room_type:N",
                scale=alt.Scale(scheme="tableau10"),
                legend=alt.Legend(title="Room Type")
            ),
            alt.value("lightgray")
        ),
        size=alt.Size(
            "accommodates:Q",
            scale=alt.Scale(range=[20, 160]),
            legend=None
        ),
        tooltip=[
            alt.Tooltip("name:N", title="Listing"),
            alt.Tooltip("price:Q", format="$.0f", title="Price/Night"),
            alt.Tooltip("review_scores_rating:Q", format=".2f", title="Rating"),
            alt.Tooltip("accommodates:Q", title="Guests"),
            alt.Tooltip("room_type:N", title="Room Type"),
            alt.Tooltip("neighbourhood_cleansed:N", title="ZIP Code")
        ]
    )
    .add_params(brush)
    .properties(
        width=440,
        height=350,
        title="Price vs. Review Score (drag to select)"
    )
)

# Chart 2b: Median price by neighborhood — responds to the brush above
neighborhood_bar = (
    alt.Chart(sample_linked)
    .mark_bar()
    .encode(
        x=alt.X("median_price:Q", title="Median Price ($/night)"),
        y=alt.Y(
            "neighbourhood_cleansed:N",
            sort="-x",
            title="ZIP Code",
            axis=alt.Axis(labelLimit=100)
        ),
        color=alt.Color(
            "median_price:Q",
            scale=alt.Scale(scheme="orangered"),
            legend=None
        ),
        tooltip=[
            alt.Tooltip("neighbourhood_cleansed:N", title="ZIP Code"),
            alt.Tooltip("median_price:Q", format="$.0f", title="Median Price"),
            alt.Tooltip("listing_count:Q", title="Listings in Selection")
        ]
    )
    .transform_filter(brush)
    .transform_aggregate(
        median_price="median(price)",
        listing_count="count()",
        groupby=["neighbourhood_cleansed"]
    )
    .transform_window(
        rank="rank(median_price)",
        sort=[alt.SortField("median_price", order="descending")]
    )
    .transform_filter(alt.datum.rank <= 10)
    .properties(
        width=380,
        height=350,
        title="Top 10 ZIPs by Median Price (brushed selection)"
    )
)

# Horizontally concatenate — both charts share the same brush parameter
linked_charts = scatter | neighborhood_bar
# Display the linked chart pair as a single composed Altair spec
st.altair_chart(linked_charts, use_container_width=True)

st.divider()

# ── CHARTS 4 & 5: Room type count + price distribution ───────────────────────
st.subheader("Room Type Breakdown")

# Count of listings by ROOM_TYPE
room_count_bar = (
    alt.Chart(filtered)
    .mark_bar()
    .encode(
        x=alt.X("room_type:N", title="Room Type", sort="-y"),
        y=alt.Y("count():Q", title="Number of Listings"),
        color=alt.Color(
            "room_type:N",
            scale=alt.Scale(scheme="tableau10"),
            legend=None
        ),
        tooltip=[
            alt.Tooltip("room_type:N", title="Room Type"),
            alt.Tooltip("count():Q", title="Listings")
        ]
    )
    .properties(width=360, height=280, title="Listing Count by Room Type")
)

# Price distribution by ROOM_TYPE as a boxplot
room_price_box = (
    alt.Chart(filtered)
    .mark_boxplot(extent="min-max", size=35)
    .encode(
        x=alt.X("room_type:N", title="Room Type"),
        y=alt.Y(
            "price:Q",
            title="Price ($/night)",
            scale=alt.Scale(zero=False)
        ),
        color=alt.Color(
            "room_type:N",
            scale=alt.Scale(scheme="tableau10"),
            legend=None
        )
    )
    .properties(width=360, height=280, title="Price Distribution by Room Type")
)

# Display the room type charts side by side
st.altair_chart(room_count_bar | room_price_box, use_container_width=True)

# Footer
st.caption(
    "Data: Inside Airbnb — Austin, TX | "
    "Dashboard built with Streamlit + Altair | "
    "Data Visualization and Storytelling, Boston College"
)
