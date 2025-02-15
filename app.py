import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from utils import InsightGenerator, AnalysisResponse

# Initialize generator
generator = InsightGenerator()

# Sample table metadata
table_metadata = {
    "sales_data": ["product_id", "product_name", "sales_amount", "sale_date", "region"],
    "product_info": ["product_id", "category", "price"],
}

st.title("AI-Driven Business Insights")
st.write("*Ask questions about your data and get insights!*")

# Suggested prompts
suggested_prompts = [
    "What are the top selling products?",
    "Compare sales across different regions",
    "Which product category generates highest revenue?",
]

# Add this near the top of the file after initializing session state for messages

st.session_state.messages = []
# if "messages" not in st.session_state:
#     st.session_state.messages = []
if "selected_prompt" not in st.session_state:
    st.session_state.selected_prompt = None

# Replace the suggested prompts section with this updated code
# st.write("*Suggested prompts*")
cols = st.columns(len(suggested_prompts))
for i, prompt in enumerate(suggested_prompts):
    if cols[i].button(prompt, key=f"prompt_{i}"):
        st.session_state.selected_prompt = prompt

# Update the query handling
chat_input = st.chat_input("Enter your query:", key="chat_input")
query = st.session_state.selected_prompt or chat_input

if query:
    # Reset selected prompt after processing
    st.session_state.selected_prompt = None
    
    # Add the user message immediately
    st.session_state.messages.append({"role": "user", "content": query})
    
    # Create a placeholder for the loading indicator
    with st.status("🤖 Analyzing your query...", expanded=True) as status:
        
        # Process the query
        response: AnalysisResponse = generator.generate_insights(query, table_metadata)
        
        insights_list = []
        
        if response.response_type == "info":
            insights_list.append({
                "insight": response.answer,
                "visualizations": [],
            })
        elif response.response_type == "analysis":
            for insight in response.insights:
                insights_list.append({
                    "insight": insight.insight,
                    "visualizations": [
                        {
                            "type": insight.visualization,
                            "data": pd.DataFrame({"x": range(10), "y": range(10)}),
                            "x_label": insight.metrics[0] if len(insight.metrics) > 0 else None,
                            "y_label": insight.metrics[1] if len(insight.metrics) > 1 else None,
                        }
                    ],
                    "sql_query": insight.sql_query
                })
        elif response.response_type == "error":
            insights_list.append({
                "insight": f"❌ {response.answer}",
                "visualizations": []
            })
        else:
            insights_list.append({
                "insight": "❌ Error: " + response.answer,
                "visualizations": [],
                "sql_query": response.sql_query
            })
        
        for item in insights_list:
            message = {
                "role": "assistant",
                "content": f"**Insight:** {item['insight']}\n\n**SQL Query:** {item['sql_query']}",
                "visualizations": item["visualizations"],
            }

            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if message["role"] == "assistant" and "visualizations" in message:
                    for viz in message["visualizations"]:
                        if viz["type"].lower() == "line_chart":
                            st.line_chart(
                                viz["data"],
                                x_label=str(viz["x_label"]),
                                y_label=str(viz["y_label"]),
                            )
                        elif viz["type"].lower() == "bar_chart":
                            st.bar_chart(
                                viz["data"],
                                x_label=str(viz["x_label"]),
                                y_label=str(viz["y_label"]),
                            )
                        elif viz["type"].lower() == "heatmap":
                            fig, ax = plt.subplots()
                            sns.heatmap(viz["data"].corr(), ax=ax)
                            st.pyplot(fig)
