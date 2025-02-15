import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import sqlite3
from utils import InsightGenerator, AnalysisResponse

# Initialize generator
generator = InsightGenerator()

# Connect to SQLite database
conn = sqlite3.connect("data_insights.db")

# Sample table metadata
table_metadata = {
    "sales_data": ["product_id", "sales_amount", "sale_date", "region"],
    "product_info": ["product_id", "product_name", "category", "price"],
}

st.title("AI-Driven Business Insights")
st.write("*Ask questions about your data and get insights!*")

# Suggested prompts
suggested_prompts = [
    "What are the top selling products?",
    "Compare sales across different regions",
    "Which product category generates highest revenue?",
]

st.session_state.messages = []
if "selected_prompt" not in st.session_state:
    st.session_state.selected_prompt = None

cols = st.columns(len(suggested_prompts))
for i, prompt in enumerate(suggested_prompts):
    if cols[i].button(prompt, key=f"prompt_{i}"):
        st.session_state.selected_prompt = prompt

chat_input = st.chat_input("Enter your query:", key="chat_input")
query = st.session_state.selected_prompt or chat_input

if query:
    st.session_state.selected_prompt = None
    st.session_state.messages.append({"role": "user", "content": query})

    with st.status("🤖 Analyzing your query...", expanded=True) as status:
        response: AnalysisResponse = generator.generate_insights(query, table_metadata)
        insights_list = []

        if response.response_type == "info":
            insights_list.append(
                {
                    "insight": response.answer,
                    "visualizations": [],
                }
            )
        elif response.response_type == "analysis":
            for insight in response.insights:
                try:
                    # Execute SQL query
                    df = pd.read_sql_query(insight.sql_query, conn)

                    # Clean column names by removing table prefixes
                    df.columns = [
                        col.split(".")[-1] if "." in col else col for col in df.columns
                    ]

                    # Get clean metric names
                    x_label = (
                        insight.metrics[0].split(".")[-1]
                        if insight.metrics and "." in insight.metrics[0]
                        else insight.metrics[0]
                    )
                    y_label = (
                        insight.metrics[1].split(".")[-1]
                        if len(insight.metrics) > 1 and "." in insight.metrics[1]
                        else insight.metrics[1]
                        if len(insight.metrics) > 1
                        else None
                    )

                    insights_list.append(
                        {
                            "insight": insight.insight,
                            "visualizations": [
                                {
                                    "type": insight.visualization,
                                    "data": df,
                                    "x_label": x_label,
                                    "y_label": y_label,
                                }
                            ],
                            "sql_query": insight.sql_query,
                        }
                    )
                except Exception as e:
                    insights_list.append(
                        {
                            "insight": f"❌ Error processing visualization: {str(e)}",
                            "visualizations": [],
                        }
                    )
        elif response.response_type == "error":
            insights_list.append(
                {
                    "insight": f"❌ {response.answer}",
                    "visualizations": [],
                }
            )
        else:
            insights_list.append(
                {
                    "insight": "❌ Error: " + response.answer,
                    "visualizations": [],
                }
            )

        for item in insights_list:
            message = {
                "role": "assistant",
                "content": f"**Insight:** {item['insight']}\n\n",
                "visualizations": item["visualizations"],
            }

            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                for viz in message["visualizations"]:
                    if (
                        viz["type"].lower() == "line_chart"
                        and viz["x_label"]
                        and viz["y_label"]
                    ):
                        st.line_chart(
                            viz["data"].set_index(viz["x_label"]), y=viz["y_label"]
                        )
                    elif (
                        viz["type"].lower() == "bar_chart"
                        and viz["x_label"]
                        and viz["y_label"]
                    ):
                        st.bar_chart(
                            viz["data"].set_index(viz["x_label"]), y=viz["y_label"]
                        )
                    elif viz["type"].lower() == "heatmap":
                        fig, ax = plt.subplots()
                        sns.heatmap(viz["data"].corr(), ax=ax)
                        st.pyplot(fig)

conn.close()
