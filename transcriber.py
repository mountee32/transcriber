import feedparser
import json
import time
import os
import requests
#import whisper
import openai  
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
from loguru import logger


load_dotenv()
# Load the Whisper model
# model = whisper.load_model("base")
openai.api_key = os.getenv('OPENAI_KEY') 

def send_email_with_attachments(to_addresses, subject, body, files):
    from_address = os.getenv('EMAIL')
    password = os.getenv('PASSWORD')

    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    for file in files:
        attachment = open(file, 'rb')

        part = MIMEBase('application', 'octet-stream')
        part.set_payload((attachment).read())
        encoders.encode_base64(part)

        part.add_header('Content-Disposition', f"attachment; filename= {file}") 

        msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_address, password)

        # Separate the recipients and send the email to each one
        for to_address in to_addresses.split(','):
            msg['To'] = to_address.strip()  # Set the 'To' field for each recipient
            text = msg.as_string()
            server.sendmail(from_address, to_address, text)

        server.quit()
        logger.info("Email sent successfully")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

def download_audio(url, filename):
    """Downloads an audio file from a URL and saves it to a file."""
    response = requests.get(url)
    response.raise_for_status()  # Throw an error if the request failed
    with open(filename, 'wb') as f:
        f.write(response.content)
    logger.info("Audio downloaded successfully")

def transcribe_audio(filename):
    """Transcribes an audio file using the Whisper service running in Docker."""

    # Define the URL of the Whisper service
    whisper_service_url = "http://172.18.0.22:9000/asr"

    # Open the file in binary mode and send a POST request to the Whisper service
    with open(filename, 'rb') as f:
        response = requests.post(whisper_service_url, files={'audio_file': f})
        
    response.raise_for_status()  # Throw an error if the request failed

    # Get the response text
    transcription = response.text.strip()
    logger.info("Audio transcribed successfully")
    return transcription

def summarize_transcription(transcription):
    """Summarizes a transcription using the OpenAI API."""
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k", 
        messages=[
            {"role": "system", "content" : "You are a chatbot which can summarize long documents."},
            {"role": "user", "content" : f"Please summarize this Christian sermon into the following format 1) Summary of 100 words, 2)20 bullet points of a total of 800 words 3) list of bible verses mentioned: {transcription}"},
        ]
    )
    logger.info("Transcription summarized successfully")
    return completion.choices[0].message['content']

def process_new_episodes():
    # Load the previous episodes
    try:
        with open("previous_episodes.json", "r") as f:
            previous_episodes = json.load(f)
    except FileNotFoundError:
        previous_episodes = []

    # Parse the RSS feed
    feed = feedparser.parse(os.getenv('PODCAST'))

    logger.info(f"Feed entries: {len(feed.entries)}")

    for entry in feed.entries:
        # Check if this episode has beenI apologize for the cutoff. Here is the rest of the code:


        # processed before
        if entry.id in previous_episodes:
            logger.info(f"Skipping processed episode: {entry.title}")
            continue

        logger.info(f"Processing new episode: {entry.title}")
        logger.info(f"Description: {entry.description}")

        # Download the audio file
        audio_url = entry.enclosures[0].href
        audio_filename = f"{entry.id}.mp3"
        download_audio(audio_url, audio_filename)

        # Transcribe the audio
        transcript = transcribe_audio(audio_filename)

        # Save the transcript to a file
        transcript_filename = f"{entry.id}.txt"
        with open(f"{entry.id}.txt", "w") as f:
            f.write(transcript)

        # Summarize the transcript
        summary = summarize_transcription(transcript)

        # Save the summary to a file
        summary_filename = f"{entry.id}_summary.txt"
        with open(f"{entry.id}_summary.txt", "w") as f:
            f.write(summary)

        # Send the transcription and summary by email
        send_email_with_attachments(
            os.getenv('TOEMAIL'),  
            f"New podcast episode: {entry.title}",
            "Here are the transcription and summary of the new podcast episode.",
            [transcript_filename, summary_filename]
        )    

        # Delete the audio file
        os.remove(audio_filename)

        # Remember that this episode has been processed
        previous_episodes.append(entry.id)
        with open("previous_episodes.json", "w") as f:
            json.dump(previous_episodes, f)

        logger.info(f"Episode {entry.title} processed successfully")

if __name__ == "__main__":
    while True:
        try:
            logger.info("Starting process")
            process_new_episodes()
            logger.info("Process finished")
        except Exception as e:
            logger.error(f"An error occurred: {e}\n{traceback.format_exc()}")
        finally:
            time.sleep(30 * 60)  # sleep for 30 minutes
