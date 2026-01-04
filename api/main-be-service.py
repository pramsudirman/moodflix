from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests
import urllib.parse  # For URL encoding
from bs4 import BeautifulSoup
import config # Import the config file

# Set up Gemini API key
genai.configure(api_key=config.GEMINI_API_KEY)  # Replace with your actual Gemini API key
model = genai.GenerativeModel("gemini-1.5-pro")

# Set up OMDb API key
omdb_api_key = config.OMDB_API_KEY  # Replace with your actual OMDb API key

app = Flask(__name__)
allowed_origins = ['https://moodflix-tau.vercel.app']
CORS(app, origins=allowed_origins)


def get_movie_recommendations(day_of_week, mood, attention_span, subtitles):
    """
    Generates movie title recommendations using the Gemini API.

    Args:
        day_of_week (str): Day of the week (e.g., "Monday", "Tuesday").
        mood (str): User's current mood (e.g., "happy", "sad", "adventurous", "relaxed", "anxious").
        attention_span (str): User's attention span ("long" or "short").
        subtitles (bool): Whether the user is open to movies with subtitles.

    Returns:
        list: A list of up to 5 movie titles.
    """

    prompt = f"""
    Today is {day_of_week}. I am feeling {mood}. 
    I have a {attention_span} attention span and I {'do not want' if not subtitles else 'am open to'} watch movies with subtitles. 
    Please provide a list of 5 movie or series titles that I might enjoy, separated by commas.
    """

    response = model.generate_content(prompt)
    recommendations = response.text.strip().split(",")  # Split by comma
    return [title.strip() for title in recommendations]  # Clean up whitespace

def get_streaming_platforms(movie_title):
    """
    Scrapes Google search results to find streaming platforms for a movie in Indonesia.
    """
    query = f"{movie_title} bisa nonton dimana indonesia"
    url = f"https://www.google.com/search?q={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }

    acceptable_platforms = {
        "Netflix", "Disney+", "Hotstar", "Prime Video", "HBO", "AppleTV", 
        "Viu", "Vidio", "Vision+", "Catchplay", "Mubi", "Klikfilm"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes

        soup = BeautifulSoup(response.content, "html.parser")

        platforms = set()
        for result in soup.find_all("span", class_="VuuXrf"):  # Find spans with the class "VuuXrf"
            platform = result.text.strip()
            if platform in acceptable_platforms:
                platforms.add(platform)

        return list(platforms) if platforms else ["Unvailable in Indonesia"]

    except requests.exceptions.RequestException as e:
        print(f"Error fetching search results for {movie_title}: {e}")
        return ["Unvailable in Indonesia"]  # Or handle the error as you prefer

@app.route('/get_recommendations')
def get_recommendations_api():
    day_of_week = request.args.get('dayOfWeek')
    mood = request.args.get('mood')
    attention_span = request.args.get('attentionSpan')
    subtitles = request.args.get('subtitles').lower() == 'true'

    recommendations = get_movie_recommendations(day_of_week, mood, attention_span, subtitles)

    movie_data = []
    for title in recommendations:
        try:
            # URL encode the title for the OMDb API request
            encoded_title = urllib.parse.quote_plus(title)

            # Call OMDb API to get movie details
            omdb_url = f"http://www.omdbapi.com/?t={encoded_title}&apikey={omdb_api_key}"
            response = requests.get(omdb_url)
            response.raise_for_status()  # Raise an exception for bad status codes
            data = response.json()

            if data.get("Response") == "True":
                movie_info = {
                    "title": data["Title"],
                    "year": data["Year"],
                    "plot": data["Plot"],
                    "poster": data["Poster"],
                    "type": data["Type"],
                    "runtime": data["Runtime"],
                    # ... other details
                }
                if data["Type"] == "series":
                    movie_info["totalSeasons"] = data["totalSeasons"]

                # Get streaming platforms
                platforms = get_streaming_platforms(title)
                movie_info["platforms"] = platforms

                movie_data.append(movie_info)
            else:
                print(f"Error getting data for {title}: {data.get('Error')}")

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from OMDb API for {title}: {e}")

    return jsonify(movie_data)

if __name__ == '__main__':
    app.run(debug=True)
