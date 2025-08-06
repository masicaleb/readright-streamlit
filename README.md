# ReadRight Streamlit App

This repository contains a Streamlit implementation of the **ReadRight** application.  It is a Python port of the original Next.js/React glassmorphism application included in this repository.  The app allows educators to adapt instructional text to different grade levels using AI and provides a history and analytics of all adaptations.

## Features

- **Supabase Authentication** – sign up or sign in using your email and password.  Sessions are persisted in the browser via Streamlit's session state.
- **Text Adaptation** – paste text or upload a `.txt`/`.md` file and select the target grade level.  Additional options allow you to simplify vocabulary, add definitions, split into short paragraphs, add visual breaks and generate comprehension questions.
- **AI-Powered** – adaptation is handled by an existing Supabase Edge Function which communicates with OpenAI.  No API keys are required in the Streamlit frontend.
- **History and Analytics** – view past adaptations and basic statistics such as total adaptations, words processed and grade distribution.  You can filter your history by grade or model and download individual adaptation summaries.

## Running Locally

1. **Install dependencies** using pip:

   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables**.  The app needs the base URL and anon key for your Supabase project as well as the slug of the Edge Function.  You can set these in your shell before running:

   ```bash
   export SUPABASE_URL="https://your-project.supabase.co"
   export SUPABASE_ANON_KEY="your-anon-key"
   export FUNCTION_SLUG="make-server-f7050fc0"
   ```

   If no variables are provided the defaults from the original project are used.  The `FUNCTION_SLUG` identifies the Supabase Edge Function defined in `supabase/functions/server` of the original code.  Do not include `/functions/v1` or any route segments in this value.

3. **Run the app**:

   ```bash
   streamlit run streamlit_app.py
   ```

4. **Sign up or sign in**.  In the sidebar choose *Sign up* to create a new account or *Sign in* to use an existing one.  After authentication you'll be able to adapt text and view your history.

## Deploying on Streamlit Cloud with GitHub

1. Push the contents of this repository to a new GitHub repository (e.g. `readright-streamlit`).  You can create the repository through the GitHub web interface and upload the files directly or use git locally.
2. Navigate to [share.streamlit.io](https://share.streamlit.io/) and sign in with your GitHub account.
3. Click *New app* and choose your repository and branch.  Set the main file to `streamlit_app.py`.
4. Under *Advanced settings* add two secrets: `SUPABASE_URL` and `SUPABASE_ANON_KEY` with the values from your Supabase project.  If you renamed the edge function then add `FUNCTION_SLUG` as well.
5. Deploy the app.  After a few moments it will be available at a unique URL.

## Attributions

This Streamlit port was derived from the original ReadRight glassmorphism application.  The original code includes a detailed attribution of third‑party assets in `Attributions.md`.