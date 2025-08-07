import os
from typing import Optional, Dict, Any, List

import streamlit as st
import requests
from supabase import create_client, Client

"""
This file implements a Streamlit version of the ReadRight application.
Users can sign up or sign in via Supabase Auth, paste or upload text,
configure adaptation settings, and call a Supabase Edge Function to
adapt the text. Adaptation history and analytics can also be viewed.

To run this app locally set the following environment variables or
configure them as Streamlit secrets when deploying on Streamlit Cloud:

  SUPABASE_URL: base URL of your Supabase project.
  SUPABASE_ANON_KEY: public anon key for your Supabase project.
  FUNCTION_SLUG: slug of the Supabase Edge Function (defaults to
                 "make-server-f7050fc0").
"""

# -----------------------------------------------------------------------------
# Configuration and helpers
# -----------------------------------------------------------------------------

# Default Supabase credentials pulled from the original Next.js app.
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://kplxzwwckwlsqusgipvx.supabase.co")
SUPABASE_ANON_KEY = os.getenv(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtwbHh6d3dja3dsc3F1c2dpcHZ4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQ1MDU4NzYsImV4cCI6MjA3MDA4MTg3Nn0.36VMlDwtVAbqRMxlitIbHhKLQT9j_i_aXe0tyfmR14E",
)

# Slug for the Edge Function; update if you rename the function.
FUNCTION_SLUG = os.getenv("FUNCTION_SLUG", "make-server-f7050fc0")


def init_supabase() -> Client:
    """Initialises and caches a Supabase client in session state."""
    if "supabase_client" not in st.session_state:
        st.session_state.supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return st.session_state.supabase_client


def sign_in(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Sign in a user and return session and user on success or None."""
    supabase = init_supabase()
    result = supabase.auth.sign_in_with_password({"email": email, "password": password})
    if result.session is None:
        return None
    return {"session": result.session, "user": result.user}


def sign_up(name: str, email: str, password: str) -> Optional[Dict[str, Any]]:
    """Create a new user and return session and user on success or None."""
    supabase = init_supabase()
    result = supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": {"data": {"name": name}},
    })
    if result.session is None:
        return None
    return {"session": result.session, "user": result.user}


def sign_out() -> None:
    """Sign out the current user and clear cached data."""
    supabase = init_supabase()
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for key in ["session", "user", "history_cache", "analytics_cache"]:
        st.session_state.pop(key, None)


def call_function(path: str, token: str, body: Optional[Dict[str, Any]] = None) -> Any:
    """
    Invoke a route on the Supabase Edge Function and return the JSON response.

    This helper wraps requests to the Supabase Edge Function used for text
    adaptation, history and analytics. The function will attempt to parse
    the response as JSON and, on failure, provide a helpful error message
    containing the response status and body. This improves the default
    behaviour, which previously raised a JSON decoding error like
    "Expecting value: line 1 column 1 (char 0)" when the response was empty
    or contained non‑JSON data.
    """
    url = f"{SUPABASE_URL}/functions/v1/{FUNCTION_SLUG}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        if body is not None:
            resp = requests.post(url, headers=headers, json=body)
        else:
            resp = requests.get(url, headers=headers)
    except Exception as exc:
        # Network errors or other issues reaching the endpoint
        return {"error": f"Failed to call function: {exc}"}
    # Attempt to parse JSON; if this fails return the raw text for debugging
    data: Any
    try:
        data = resp.json()
    except Exception:
        # Provide detailed feedback when the response isn't valid JSON
        text = resp.text.strip()
        if not text:
            text = "<empty response>"
        return {
            "error": f"Invalid JSON response (status {resp.status_code}). Response body: {text}"
        }
    # Non‑200 responses may still contain useful error information
    if not resp.ok:
        # Supabase functions typically return an object with an `error` field
        err = data.get("error", data)
        return {"error": err}
    return data


def adapt_text(token: str, text: str, config: Dict[str, Any]) -> Any:
    """
    Adapt the provided text based on the given configuration.

    By default this function proxies to the Supabase Edge Function at
    `/adapt-text`. If an OpenAI API key is provided via Streamlit secrets
    (`st.secrets["OPENAI_API_KEY"]`) or the `OPENAI_API_KEY` environment
    variable, the function will instead call the OpenAI Chat Completions API
    directly. This allows users to run the app without a custom Supabase
    backend and removes the dependency on a separate Edge Function.

    The configuration dictionary should contain at least the following keys:

      - gradeLevel: one of "k", "1", "2", ... "12"
      - aiModel: one of "basic", "advanced", "premium"
      - simplifyVocabulary: bool
      - addDefinitions: bool
      - shortParagraphs: bool
      - visualBreaks: bool
      - comprehensionQuestions: bool

    When calling the OpenAI API directly, the function attempts to map
    `aiModel` to an appropriate OpenAI model. You can customise this mapping
    by adjusting the `model_map` defined below.
    """
    # First check for an OpenAI API key in Streamlit secrets or env vars
    openai_key: Optional[str] = None
    try:
        # Prefer Streamlit secrets if available
        if hasattr(st, "secrets") and isinstance(st.secrets, dict):
            openai_key = st.secrets.get("OPENAI_API_KEY")  # type: ignore[attr-defined]
    except Exception:
        # Accessing st.secrets outside of a Streamlit context can raise
        pass
    if not openai_key:
        openai_key = os.getenv("OPENAI_API_KEY")

    if openai_key:
        # Map ReadRight model choices to OpenAI models. Users can
        # customise this mapping to suit their OpenAI account access.
        model_map: Dict[str, str] = {
            "basic": "gpt-3.5-turbo",
            "advanced": "gpt-3.5-turbo",
            "premium": "gpt-4",
        }
        openai_model = model_map.get(config.get("aiModel"), "gpt-3.5-turbo")
        # Build a prompt that instructs the assistant to adapt the text
        grade = config.get("gradeLevel", "3")
        user_prompt = f"Rewrite the following text for grade {grade} reading level."
        if config.get("simplifyVocabulary"):
            user_prompt += " Simplify vocabulary."
        if config.get("addDefinitions"):
            user_prompt += " Include brief definitions for complex words in parentheses immediately after the word."
        if config.get("shortParagraphs"):
            user_prompt += " Break the output into shorter paragraphs."
        if config.get("visualBreaks"):
            user_prompt += " Add visual breaks such as bullet points or separators where appropriate."
        if config.get("comprehensionQuestions"):
            user_prompt += " After the adapted text, include a few comprehension questions about the content."
        user_prompt += "\n\n" + text
        system_prompt = (
            "You are a helpful assistant that adapts educational text for teachers. "
            "Given a target reading grade level and a piece of text, you rewrite "
            "the text to match the specified grade while preserving the original meaning."
        )
        payload = {
            "model": openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            # Some sensible defaults; you can tweak temperature or max_tokens
            "temperature": 0.7,
            "max_tokens": 1024,
        }
        headers = {
            "Authorization": f"Bearer {openai_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
        except Exception as exc:
            return {"error": f"Failed to call OpenAI API: {exc}"}
        if not resp.ok:
            # If the API returns an error, surface the status and body
            body = resp.text.strip() or "<empty response>"
            return {"error": f"OpenAI API error (status {resp.status_code}): {body}"}
        try:
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return {"error": "OpenAI API returned no choices."}
            adapted = choices[0]["message"]["content"].strip()
            meta: Dict[str, Any] = {
                "model": openai_model,
            }
            # Include token usage metadata if available
            if "usage" in data:
                meta.update({
                    "promptTokens": data["usage"].get("prompt_tokens"),
                    "completionTokens": data["usage"].get("completion_tokens"),
                    "totalTokens": data["usage"].get("total_tokens"),
                })
            return {"adaptedText": adapted, "metadata": meta}
        except Exception as exc:
            return {"error": f"Failed to parse OpenAI response: {exc}"}
    # No OpenAI key: fall back to Supabase Edge Function
    return call_function("/adapt-text", token, {"text": text, "config": config})


def fetch_history(token: str) -> Any:
    """Proxy for the history endpoint."""
    return call_function("/history", token)


def fetch_analytics(token: str) -> Any:
    """Proxy for the analytics endpoint."""
    return call_function("/analytics", token)


def main() -> None:
    st.set_page_config(page_title="ReadRight", page_icon="📚", layout="wide")

    # Initialise Supabase client
    init_supabase()

    # Sidebar: authentication
    st.sidebar.title("ReadRight")
    if st.session_state.get("session") is None:
        # Show sign-in and sign-up forms
        tabs = st.sidebar.tabs(["Sign in", "Sign up"])
        with tabs[0]:
            st.subheader("Sign in")
            email = st.text_input("Email", key="signin_email")
            password = st.text_input("Password", type="password", key="signin_password")
            if st.button("Sign in", key="signin_button"):
                if not email or not password:
                    st.warning("Please provide email and password")
                else:
                    try:
                        result = sign_in(email, password)
                        if result is None:
                            st.error("Invalid credentials or email confirmation required")
                        else:
                            st.session_state.session = result["session"]
                            st.session_state.user = result["user"]
                            st.success("Signed in successfully")
                    except Exception as exc:
                        st.error(f"Sign in failed: {exc}")
        with tabs[1]:
            st.subheader("Sign up")
            name = st.text_input("Name", key="signup_name")
            email_up = st.text_input("Email", key="signup_email")
            password_up = st.text_input("Password", type="password", key="signup_password")
            if st.button("Sign up", key="signup_button"):
                if not name or not email_up or not password_up:
                    st.warning("Please fill in all fields")
                else:
                    try:
                        result = sign_up(name, email_up, password_up)
                        if result is None:
                            st.info("Sign up successful. Please check your email to confirm your account.")
                        else:
                            st.session_state.session = result["session"]
                            st.session_state.user = result["user"]
                            st.success("Account created and signed in successfully")
                    except Exception as exc:
                        st.error(f"Sign up failed: {exc}")
    else:
        # Show logged-in user info
        st.sidebar.write(f"Signed in as **{st.session_state.user.email}**")
        if st.sidebar.button("Sign out", key="signout_button"):
            sign_out()
            st.experimental_rerun()

    # Require authentication for the remainder of the app
    if st.session_state.get("session") is None:
        st.header("Welcome to ReadRight")
        st.write(
            """
            Sign in or create an account from the sidebar to begin using the
            AI-powered text adaptation features. Once logged in you'll be able
            to paste or upload text, choose a reading level and other options,
            and receive adapted content.
            """
        )
        return

    # Prepare configuration inputs in the sidebar
    st.sidebar.header("Configuration")
    grade_levels = {
        "k": "Kindergarten",
        "1": "1st Grade",
        "2": "2nd Grade",
        "3": "3rd Grade",
        "4": "4th Grade",
        "5": "5th Grade",
        "6": "6th Grade",
        "7": "7th Grade",
        "8": "8th Grade",
        "9": "9th Grade",
        "10": "10th Grade",
        "11": "11th Grade",
        "12": "12th Grade",
    }
    grade_keys: List[str] = list(grade_levels.keys())
    default_grade_idx = grade_keys.index("2")
    grade = st.sidebar.selectbox(
        "Target grade level",
        grade_keys,
        format_func=lambda k: grade_levels[k],
        index=default_grade_idx,
        key="grade_level",
    )
    model_options = {
        "basic": "Basic (fast)",
        "advanced": "Advanced (balanced)",
        "premium": "Premium (highest quality)",
    }
    model_keys: List[str] = list(model_options.keys())
    model = st.sidebar.selectbox(
        "Processing model",
        model_keys,
        format_func=lambda m: model_options[m],
        index=1,
        key="ai_model",
    )
    st.sidebar.subheader("Accessibility options")
    simplify_vocabulary = st.sidebar.checkbox("Simplify vocabulary", value=True, key="simplify_vocab")
    add_definitions = st.sidebar.checkbox("Add definitions", value=True, key="add_defs")
    short_paragraphs = st.sidebar.checkbox("Short paragraphs", value=True, key="short_paras")
    visual_breaks = st.sidebar.checkbox("Add visual breaks", value=False, key="visual_breaks")
    st.sidebar.subheader("Output options")
    comprehension_questions = st.sidebar.checkbox("Generate comprehension questions", value=True, key="comp_questions")
    config = {
        "gradeLevel": grade,
        "aiModel": model,
        "simplifyVocabulary": simplify_vocabulary,
        "addDefinitions": add_definitions,
        "shortParagraphs": short_paragraphs,
        "visualBreaks": visual_breaks,
        "comprehensionQuestions": comprehension_questions,
    }

    # Tabs for different sections
    tabs = st.tabs(["Adapt text", "Analytics", "History"])

    # Adapt Text Tab
    with tabs[0]:
        st.header("Adapt text")
        st.write("Enter or upload the content you would like to adapt.")
        input_text = st.text_area("Input text", height=250, key="input_text")
        # Limit uploads to plain text formats. Microsoft Word formats are not
        # supported natively by this app and will be treated as binary if
        # uploaded. For best results use .txt or .md files.
        uploaded_file = st.file_uploader("Upload a text file", type=["txt", "md"], key="file_uploader")
        if uploaded_file is not None:
            try:
                content_bytes = uploaded_file.read()
                try:
                    file_text = content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    file_text = content_bytes.decode("latin-1")
                st.session_state.input_text = file_text
                st.success(f"Loaded {uploaded_file.name} ({len(file_text)} characters)")
                input_text = file_text
            except Exception as exc:
                st.error(f"Failed to read file: {exc}")
        words = len(input_text.split()) if input_text.strip() else 0
        reading_time = (words + 199) // 200 if words else 0
        st.caption(f"Word count: {words} • Estimated reading time: {reading_time} min")
        col_a, col_b = st.columns(2)
        adapt_clicked = col_a.button("Adapt text", disabled=not input_text.strip(), key="adapt_button")
        clear_clicked = col_b.button("Clear input", disabled=not input_text, key="clear_input")
        if clear_clicked:
            st.session_state.input_text = ""
            st.experimental_rerun()
        if "output_text" not in st.session_state:
            st.session_state.output_text = ""
            st.session_state.metadata = None
        if adapt_clicked:
            with st.spinner("Adapting text using AI..."):
                result = adapt_text(st.session_state.session.access_token, input_text, config)
                if isinstance(result, dict) and result.get("error"):
                    st.error(f"Adaptation failed: {result['error']}")
                else:
                    st.session_state.output_text = result.get("adaptedText", "")
                    st.session_state.metadata = result.get("metadata", {})
                    st.success("Text adapted successfully!")
        st.subheader("Adapted text")
        if st.session_state.output_text:
            st.text_area("", value=st.session_state.output_text, height=250, key="output_text_area")
            cc1, cc2, cc3 = st.columns(3)
            if cc1.button("Copy", key="copy_output"):
                # Note: Streamlit does not yet provide a direct clipboard API. We
                # notify the user to copy manually from the output text area.
                st.success("Select the adapted text and copy it using your keyboard.")
            cc2.download_button(
                label="Download",
                data=st.session_state.output_text,
                file_name=f"adapted-text-grade-{grade}.txt",
                mime="text/plain",
                key="download_output",
            )
            if cc3.button("Clear output", key="clear_output"):
                st.session_state.output_text = ""
                st.session_state.metadata = None
                st.experimental_rerun()
            if st.session_state.metadata:
                md = st.session_state.metadata
                st.caption(
                    f"Processed in {md.get('processingTime', 'n/a')} • Tokens used: {md.get('tokensUsed', 'n/a')} "
                    f"• Model: {md.get('model', model)}"
                )
        else:
            st.info("The adapted text will appear here once processing completes.")

    # Analytics Tab
    with tabs[1]:
        st.header("Analytics")
        if st.button("Refresh analytics", key="refresh_analytics") or st.session_state.get("analytics_cache") is None:
            with st.spinner("Fetching analytics..."):
                data = fetch_analytics(st.session_state.session.access_token)
                if isinstance(data, dict) and data.get("error"):
                    st.error(f"Failed to fetch analytics: {data['error']}")
                    st.session_state.analytics_cache = None
                else:
                    st.session_state.analytics_cache = data
        analytics_data = st.session_state.get("analytics_cache")
        if analytics_data:
            stats = analytics_data.get("stats", {})
            weekly = analytics_data.get("weeklyUsage", [])
            recent = analytics_data.get("recentActivity", [])
            col1, col2 = st.columns([1, 2])
            with col1:
                st.subheader("Summary")
                st.metric("Total adaptations", stats.get("totalAdaptations", 0))
                st.metric("Total words adapted", stats.get("totalWords", 0))
                st.metric("Total tokens used", stats.get("totalTokens", 0))
                grade_breakdown = stats.get("gradeBreakdown", {})
                if grade_breakdown:
                    st.markdown("**Adaptations by grade**")
                    chart_data = {"Grade": list(grade_breakdown.keys()), "Count": list(grade_breakdown.values())}
                    st.bar_chart(chart_data, x="Grade", y="Count")
            with col2:
                if weekly:
                    st.subheader("Last 4 weeks usage")
                    week_labels = [item["week"] for item in weekly]
                    adaptations = [item["adaptations"] for item in weekly]
                    words_week = [item["words"] for item in weekly]
                    st.line_chart({"Adaptations": adaptations, "Words": words_week}, x=week_labels)
            st.subheader("Recent activity")
            if recent:
                for entry in recent:
                    grade_disp = grade_levels.get(entry["config"].get("gradeLevel"), entry["config"].get("gradeLevel"))
                    model_disp = entry["config"].get("aiModel")
                    st.markdown(
                        f"**{entry.get('timestamp', '')[:10]}** — {entry.get('wordCount', 0)} words, Grade {grade_disp}, Model {model_disp}."
                    )
            else:
                st.info("No recent adaptations in the last 30 days.")
        else:
            st.info("No analytics data available. Try adapting some text first.")

    # History Tab
    with tabs[2]:
        st.header("History")
        if st.button("Refresh history", key="refresh_history") or st.session_state.get("history_cache") is None:
            with st.spinner("Fetching history..."):
                data = fetch_history(st.session_state.session.access_token)
                if isinstance(data, dict) and data.get("error"):
                    st.error(f"Failed to fetch history: {data['error']}")
                    st.session_state.history_cache = None
                else:
                    st.session_state.history_cache = data.get("history", [])
        history_data = st.session_state.get("history_cache", [])
        if history_data:
            search = st.text_input("Search", key="history_search")
            grade_filter = st.selectbox(
                "Grade", ["all"] + grade_keys, format_func=lambda x: "All" if x == "all" else grade_levels[x], key="history_grade_filter"
            )
            model_filter = st.selectbox(
                "Model", ["all"] + model_keys, format_func=lambda x: "All" if x == "all" else x.capitalize(), key="history_model_filter"
            )
            filtered = history_data
            if search:
                filtered = [entry for entry in filtered if search.lower() in entry.get("originalText", "").lower() or search.lower() in entry.get("adaptedText", "").lower()]
            if grade_filter != "all":
                filtered = [entry for entry in filtered if entry["config"].get("gradeLevel") == grade_filter]
            if model_filter != "all":
                filtered = [entry for entry in filtered if entry["config"].get("aiModel") == model_filter]
            if not filtered:
                st.info("No history items match your filters.")
            else:
                for entry in filtered:
                    header = f"{entry['timestamp']} — Grade {grade_levels.get(entry['config'].get('gradeLevel'), entry['config'].get('gradeLevel'))} • {entry['wordCount']} words"
                    with st.expander(header):
                        st.write("**Original text**")
                        st.text_area("", value=entry.get("originalText", ""), height=150, key=f"orig_{entry['id']}", disabled=True)
                        st.write("**Adapted text**")
                        st.text_area("", value=entry.get("adaptedText", ""), height=150, key=f"adapt_{entry['id']}", disabled=True)
                        c1, c2 = st.columns(2)
                        if c1.button("Copy adapted", key=f"copy_{entry['id']}"):
                            st.success("Select the adapted text above and copy it using your keyboard.")
                        # Compose download content
                        content = (
                            "ReadRight Text Adaptation\n\nOriginal Text:\n"
                            + entry.get("originalText", "")
                            + "\n\nAdapted Text:\n"
                            + entry.get("adaptedText", "")
                            + "\n\nSettings:\n"
                            + f"- Grade Level: {grade_levels.get(entry['config'].get('gradeLevel'), entry['config'].get('gradeLevel'))}\n"
                            + f"- AI Model: {entry['config'].get('aiModel')}\n"
                            + f"- Simplify Vocabulary: {entry['config'].get('simplifyVocabulary')}\n"
                            + f"- Add Definitions: {entry['config'].get('addDefinitions')}\n"
                            + f"- Short Paragraphs: {entry['config'].get('shortParagraphs')}\n"
                            + f"- Visual Breaks: {entry['config'].get('visualBreaks')}\n"
                            + f"- Comprehension Questions: {entry['config'].get('comprehensionQuestions')}\n\n"
                            + f"Generated: {entry.get('timestamp')}\n"
                            + f"Word Count: {entry.get('wordCount', 0)} words\n"
                        )
                        c2.download_button(
                            label="Download",
                            data=content,
                            file_name=f"readright-adaptation-{entry['id'][-8:]}.txt",
                            mime="text/plain",
                            key=f"download_{entry['id']}",
                        )
        else:
            st.info("No adaptations found yet. Try adapting some text first.")


if __name__ == "__main__":
    main()
