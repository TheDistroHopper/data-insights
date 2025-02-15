import os
import json
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Insight:
    insight: str
    business_value: str
    sql_query: str
    visualization: str
    metrics: List[str]


@dataclass
class AnalysisResponse:
    response_type: str
    insights: Optional[List[Insight]] = None
    answer: Optional[str] = None


class PromptTemplate:
    """Handles prompt generation and formatting."""

    @staticmethod
    def get_analysis_prompt(query: str, metadata_str: str) -> str:
        return f"""
        You are an expert business intelligence analyst. Analyze the following:
        
        USER QUERY: {query}
        
        AVAILABLE DATA:
        Tables and their columns:
        {metadata_str}
        
        TASK:
        1. For general questions about available insights:
           - Analyze the table structure and relationships
           - Suggest exactly one concrete, specific insight that could be generated
           - Focus on business value and actionable information
           - DO NOT ask for query refinement or say the question is too general
           
        2. For specific analysis questions:
           - Generate specific insights with SQL queries for bar chart only
           - Include business value and visualization suggestions specific
        
        OUTPUT FORMAT:
        If asking about available insights:
        {{
            "response_type": "info",
            "answer": "Based on the available data, I can provide insights about: [Insight possibility]"
        }}
        
        If asking for specific analysis:
        {{
            "response_type": "analysis",
            "insights": [
                {{
                    "insight": "Clear description of what we're looking for",
                    "business_value": "1-2 sentence explanation of why this matters",
                    "sql_query": "Optimized SQL query with properly defined X and Y columns",
                    "visualization": "bar_chart",
                    "metrics": ["X_column", "Y_column"]
                }}
            ]
        }}
        
        SQL REQUIREMENTS:
        - Use simple column names in the final SELECT statement without table prefixes
        - Format SQL queries as: 
          SELECT 
              table_name.column_name AS column_name
          FROM...
        - Ensure metrics array contains simple column names without table prefixes
        - Format metrics as ["column_name", "column_name"] not ["table_name.column_name"]
        - Always use fully qualified column names to avoid ambiguity (e.g., table_name.column_name)
        - Format SQL queries with proper spacing and line breaks
        - Each SQL clause should be on a new line
        - Use single quotes for string literals in SQL
        - Ensure all column references exist in the provided metadata
        - Use appropriate joins when combining tables based on their relationships
        - Ensure the SQL query has well-defined columns suitable for bar charts, line charts, and heatmaps
        - Validate column names before generating SQL queries.

        
        EXAMPLES:
        If user asks "What insights can you provide?", and metadata includes:
        {{
            "orders": ["order_id", "customer_id", "order_date", "total_amount"],
            "customers": ["customer_id", "customer_name", "region"]
        }}
        
        Respond with:
        {{
            "response_type": "info",
            "answer": "Based on the available data, I can provide insights about: 1) Customer purchasing trends over time (line_chart), 2) Regional revenue distribution (bar_chart), 3) Order frequency heatmap by date and region (heatmap)."
        }}
        
        Now, analyze the following query:
        {query}
        """


class InsightGenerator:
    def __init__(self, model_name="gemini-pro"):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel(model_name)

    def clean_response(self, response_text: str) -> str:
        """Cleans AI response by removing markdown formatting and fixing escape characters."""
        # Remove JSON markdown
        cleaned_text = re.sub(r"```json\s*|\s*```", "", response_text)

        # Fix SQL query concatenation by removing " + " and adding proper spacing
        cleaned_text = re.sub(r'"\s*\+\s*"', " ", cleaned_text)

        # Add spaces after commas in SQL queries
        cleaned_text = re.sub(r",(?=\w)", ", ", cleaned_text)

        cleaned_text = re.sub(
            r"\\\s", " ", cleaned_text
        )  # Remove backslash before spaces

        # Fix spacing around SQL keywords
        sql_keywords = ["SELECT", "FROM", "WHERE",
                        "GROUP BY", "ORDER BY", "JOIN", "ON"]
        for keyword in sql_keywords:
            cleaned_text = re.sub(
                rf"\b{keyword}\b(?!\s)", f"{keyword} ", cleaned_text)

        # Remove excessive whitespace while preserving SQL formatting
        cleaned_text = re.sub(r"\s+", " ", cleaned_text)
        cleaned_text = re.sub(r"\s*;\s*", ";", cleaned_text)

        # Clean up any remaining invalid JSON characters
        cleaned_text = re.sub(r"[\x00-\x1F\x7F]", "", cleaned_text)

        try:
            # Validate JSON structure
            json.loads(cleaned_text)
            return cleaned_text
        except json.JSONDecodeError as e:
            print(f"Debug - JSON parsing error: {str(e)}")
            print(f"Debug - Cleaned text causing error: {cleaned_text}")

            # Additional fix attempt for common JSON formatting issues
            # Remove quotes after numbers
            cleaned_text = re.sub(r'(?<=\d)"(?=,)', "", cleaned_text)
            # Fix multiple commas
            cleaned_text = re.sub(r",,+", ",", cleaned_text)
            # Remove trailing commas
            cleaned_text = re.sub(r",\s*}", "}", cleaned_text)

            return cleaned_text

    def parse_response(self, cleaned_response: str) -> AnalysisResponse:
        """Parses the cleaned response into structured format."""
        try:
            # First try to parse as JSON
            response_dict = json.loads(cleaned_response)

            if response_dict.get("response_type") == "info":
                return AnalysisResponse(
                    response_type="info",
                    answer=response_dict.get("answer", "No answer provided."),
                )
            elif response_dict.get("response_type") == "analysis":
                insights = [
                    Insight(**insight) for insight in response_dict.get("insights", [])
                ]
                return AnalysisResponse(response_type="analysis", insights=insights)
            else:
                return AnalysisResponse(
                    response_type="error",
                    answer=f"Unknown response type: {response_dict.get('response_type')}",
                )

        except json.JSONDecodeError as e:
            # If the response is a plain text error message, return it directly
            if "unable to generate" in cleaned_response.lower():
                return AnalysisResponse(response_type="error", answer=cleaned_response)
            # Otherwise return the parsing error
            return AnalysisResponse(
                response_type="error", answer=f"Failed to parse response: {str(e)}"
            )

    def generate_insights(
        self, query: str, table_metadata: Dict[str, list]
    ) -> AnalysisResponse:
        """Processes user query and returns structured insights."""
        metadata_str = json.dumps(table_metadata, indent=2)
        prompt = PromptTemplate.get_analysis_prompt(query, metadata_str)

        try:
            response = self.model.generate_content(prompt)
            print(response)
            if not response.text:
                return AnalysisResponse(
                    response_type="error",
                    answer="No response generated. Please try rewording your question.",
                )

            cleaned_response = self.clean_response(response.text)
            return self.parse_response(cleaned_response)

        except Exception as e:
            return AnalysisResponse(
                response_type="error", answer=f"Error generating insights: {str(e)}"
            )


class ChatInterface:
    def __init__(self, generator: InsightGenerator, table_metadata: Dict[str, list]):
        self.generator = generator
        self.table_metadata = table_metadata
        self.chat_history = []
        self.exit_commands = ["exit", "quit", "bye"]
        self.response_formatters = {
            "info": self._format_info_response,
            "analysis": self._format_analysis_response,
            "error": self._format_error_response,
        }

    def _format_info_response(self, response: AnalysisResponse) -> str:
        """Format informational responses"""
        return f"🤖 AI: {response.answer}\n"

    def _format_analysis_response(self, response: AnalysisResponse) -> str:
        """Format analysis responses with insights"""
        output = "🔹 AI-generated insights & queries:\n"
        for insight in response.insights or []:
            output += self._format_insight(insight)
        return output

    def _format_insight(self, insight: Insight) -> str:
        """Format a single insight"""
        return "\n".join(
            [
                f"\n Insight: {insight.insight}",
                f" Business Value: {insight.business_value}",
                f" Visualization: {insight.visualization}",
                f" Key Metrics: {', '.join(insight.metrics)}",
                f" SQL:\n{insight.sql_query}\n",
            ]
        )

    def _format_error_response(self, response: AnalysisResponse) -> str:
        """Format error responses"""
        return f"❌ Error: {response.answer}\n"

    def format_response(self, response: AnalysisResponse) -> str:
        """Format response based on type"""
        formatter = self.response_formatters.get(
            response.response_type, self._format_error_response
        )
        return formatter(response)

    def save_to_history(self, user_input: str, response: AnalysisResponse):
        """Save interaction to chat history"""
        self.chat_history.append(
            {"timestamp": pd.Timestamp.now(), "user": user_input, "ai": response}
        )

    def start_chat(self):
        """Run interactive chat session"""
        print("\n🔹 Business Insight Chatbot – Ask me about your data!")
        print(f"Type {', '.join(self.exit_commands)} to end the session.\n")

        while True:
            user_input = input("👤 You: ").strip().lower()
            if user_input in self.exit_commands:
                print("👋 Exiting chat. Have a great day!")
                break

            response = self.generator.generate_insights(
                user_input, self.table_metadata)
            formatted_response = self.format_response(response)
            print(formatted_response)
            self.save_to_history(user_input, response)


# Sample usage
if __name__ == "__main__":
    # Sample table metadata
    table_metadata = {
        "sales_data": [
            "product_id",
            "sales_amount",
            "sale_date",
            "region",
        ],
        "product_info": ["product_id", "product_name", "category", "price"],
    }

    # Initialize Chat Interface
    generator = InsightGenerator()
    chatbot = ChatInterface(generator, table_metadata)

    # Start chat session
    chatbot.start_chat()
