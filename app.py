import streamlit as st
import pandas as pd
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build
from openai import OpenAI
import os
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import warnings

# --- CONFIGURATION ---
warnings.filterwarnings("ignore")
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not OPENAI_API_KEY:
    st.error("OPENAI API key not found. Please set it in the .env file.")
    st.stop()

openai = OpenAI(api_key=OPENAI_API_KEY)
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)


# --- FONCTIONS ---
def extract_video_id(youtube_url):
    try:
        query = urlparse(youtube_url).query
        return parse_qs(query)['v'][0]
    except Exception:
        return None

def scrape_comments(video_id, max_comments=300):
    request = youtube.commentThreads().list(
        part="snippet",
        videoId=video_id,
        textFormat='plainText',
        maxResults=100
    )

    comments = []
    while request and len(comments) < max_comments:
        try:
            response = request.execute()
            for item in response['items']:
                comment_data = item['snippet']['topLevelComment']['snippet']
                comments.append(comment_data['textDisplay'])
            request = youtube.commentThreads().list_next(request, response)
        except Exception as e:
            print(f"Error: {e}")
            break
    return comments

def generate_summary(comments, language="English"):
    if not comments:
        return "No comments available to summarize."

    lang_instruction = {
        "English": "Write the summary in English.",
        "Français": "Rédige le résumé en français.",
        "Español": "Escribe el resumen en español."
    }

    messages = [
        {
            "role": "system",
            "content": (
                f"You are an expert language model specialized in analyzing YouTube comments. "
                "Your task is to read all the comments and produce a concise and insightful summary that reflects the general audience reaction. "
                "You must identify the main sentiments (positive or negative), recurring praises or criticisms, frequent themes, and the overall tone of the discussion. "
                "Include any relevant observations, such as common questions, moments appreciated, or points of confusion. "
                "The summary should be written in a natural and professional tone, as if reporting the audience’s feedback to the video creator. "
                "Do not list comments individually or classify them. Focus on delivering an overview. "
                f"{lang_instruction[language]}"
            )
        },
        {
            "role": "user",
            "content": "\n".join(comments[:300])
        }
    ]

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def detect_themes_and_trends(comments, language="English"):
    instruction = {
        "English": "List the top 5 recurring themes, questions or trends mentioned in the comments. Each should be concise, one line max.",
        "Français": "Liste les 5 principaux thèmes récurrents, questions ou tendances mentionnées dans les commentaires. Chaque ligne doit être concise.",
        "Español": "Enumera los 5 temas, preguntas o tendencias recurrentes que aparecen en los comentarios. Cada uno debe ser una línea como máximo."
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are a smart assistant that analyzes YouTube comments and extracts recurring themes or feedback trends. "
                "You must analyze the audience’s feedback and return a list of concise, distinct points. "
                + instruction[language]
            )
        },
        {
            "role": "user",
            "content": "\n".join(comments[:100])
        }
    ]

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.5,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error during trend detection: {str(e)}"

def generate_content_ideas(comments):
    messages = [
        {
            "role": "system",
            "content": (
                "You are an assistant helping a YouTuber plan their next videos. Analyze the following YouTube comments and generate a list of 5 content ideas that viewers would likely enjoy. "
                "These ideas should be based on questions, suggestions, repeated interests, or common feedback in the comments. Keep each idea short and actionable."
            )
        },
        {
            "role": "user",
            "content": "\n".join(comments[:100])
        }
    ]
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.6,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating content ideas: {str(e)}"

def analyze_emotions(comments):
    emotion_prompt = [
        {
            "role": "system",
            "content": (
                "You are an emotion analysis assistant. Your task is to analyze a set of YouTube comments "
                "and return a JSON-style dictionary with estimated percentages of the main emotional tones "
                "expressed in the text. The keys should be emotion categories such as: 'Joy', 'Sadness', "
                "'Anger', 'Surprise', 'Disappointment', 'Confusion', etc. The values should be approximate percentages "
                "adding up to 100%. Provide only the dictionary. Do not explain."
            )
        },
        {
            "role": "user",
            "content": "\n".join(comments[:100])
        }
    ]

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=emotion_prompt,
            temperature=0.3,
            max_tokens=300
        )
        raw_text = response.choices[0].message.content.strip()
        emotion_data = eval(raw_text)
        return emotion_data
    except Exception as e:
        return {"Error": str(e)}

def plot_emotions(emotion_data):
    if not emotion_data:
        st.write("No emotion data to display.")
        return

    labels = list(emotion_data.keys())
    values = list(emotion_data.values())

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, values)
    ax.set_ylabel("Percentage of Comments")
    ax.set_title("Emotional Tone Distribution")
    plt.xticks(rotation=25)
    st.pyplot(fig)


# --- STREAMLIT UI ---
st.set_page_config(page_title="YouTube Comment Analyzer", page_icon=None)
st.title("YouTube Comment Analyzer")

st.write("Enter a YouTube video URL to generate a summary of the comments, detect trends, and analyze audience emotions.")

youtube_url = st.text_input("YouTube Video URL", placeholder="https://www.youtube.com/watch?v=XXXXXXX")

lang_choice = st.selectbox(
    "Select the language for the summary:",
    ["English", "Français", "Español"]
)

if st.button("Analyze Comments"):
    with st.spinner("Retrieving comments..."):
        video_id = extract_video_id(youtube_url)
        if not video_id:
            st.error("Invalid YouTube URL.")
        else:
            comments = scrape_comments(video_id)
            if not comments:
                st.warning("No comments found or comments are disabled for this video.")
            else:
                with st.spinner("Generating summary..."):
                    summary = generate_summary(comments, language=lang_choice)
                    st.subheader(f"Comment Summary ({lang_choice})")
                    st.write(summary)

                with st.spinner("Detecting themes and trends..."):
                    trends = detect_themes_and_trends(comments, language=lang_choice)
                    st.subheader("Detected Topics and Trends")
                    st.write(trends)

                with st.spinner("Generating next video ideas..."):
                    ideas = generate_content_ideas(comments)
                    st.subheader("Suggested Next Video Ideas")
                    st.write(ideas)

                with st.spinner("Analyzing emotional tone..."):
                    emotion_results = analyze_emotions(comments)
                    if "Error" in emotion_results:
                        st.error(f"Emotion analysis failed: {emotion_results['Error']}")
                    else:
                        st.subheader("Emotional Tone Analysis")
                        plot_emotions(emotion_results)
