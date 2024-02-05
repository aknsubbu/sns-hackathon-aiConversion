
# Download the required packages
# !pip install --upgrade google-cloud-texttospeech
# !pip install pydub
# !pip install flask-restx
# !pip install pymongo

# !pip show flask-restx

from flask import Flask, request, jsonify
from flask_restx import Api
from pydub import AudioSegment
from pymongo import MongoClient
from gridfs import GridFS
from bson import ObjectId
from moviepy.editor import VideoFileClip, AudioFileClip, ImageSequenceClip, concatenate_videoclips
from google.cloud import texttospeech
from google.cloud import translate_v2 as translate
import os
import base64

#ffmpeg imports
# ffmpeg_path = "/Users/anandkumarns/Downloads/ffmpeg"
# ffprobe_path = "/Users/anandkumarns/Downloads/ffmpeg/ffprobe"
#gcp imports

# Set the paths for ffmpeg and ffprobe
# AudioSegment.converter = ffmpeg_path
# AudioSegment.ffmpeg = ffmpeg_path
# AudioSegment.ffprobe = ffprobe_path

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/content/speedy-lattice-405709-70ec37c10a13.json"

from google.cloud import translate_v2 as translate


def translate_text(target: str, text: str) -> dict:


    translate_client = translate.Client()

    if isinstance(text, bytes):
        text = text.decode("utf-8")

    result = translate_client.translate(text, target_language=target)

    print("Text: {}".format(result["input"]))
    print("Translation: {}".format(result["translatedText"]))
    print("Detected source language: {}".format(result["detectedSourceLanguage"]))

    return result["translatedText"]

def convert_and_upload_video(video_path, mongodb_uri, database_name, collection_name, file_name,userID):
    with open(video_path, 'rb') as video_file:
        base64_data = base64.b64encode(video_file.read()).decode('utf-8')

    # Connect to MongoDB
    client = MongoClient(mongodb_uri)
    db = client[database_name]
    fs = GridFS(db, collection=collection_name)


    video_id = fs.put(base64_data.encode('utf-8'), title=file_name,userID=userID)
    client.close()

    #check and delete
    check_and_delete_video(video_id, mongodb_uri, database_name, collection_name,file_name)
    return video_id

import os
client = texttospeech.TextToSpeechClient()
api_endpoint=''


def tts(article, langCode, title):
    synthesis_input = texttospeech.SynthesisInput(text=article)
    voice = texttospeech.VoiceSelectionParams(
        language_code=langCode,
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config)

    mp3_path = '/content/' + title  +'.mp3'

    try:
        with open(mp3_path, 'wb') as mp3_file:
            mp3_file.write(response.audio_content)
        print(f"MP3 file successfully written to {mp3_path}")
    except Exception as e:
        print(f"Error writing MP3 file: {e}")

    audio = AudioSegment.from_mp3(mp3_path)
    audio_duration_ms = len(audio) / 1000


    return audio_duration_ms

def translate_and_audio(text,langCode,title):
  translated=translate_text(langCode[0:2],text)
  return tts(translated,langCode,title)

text='this is a test for the competition'
title='translated_audio'
langCode='ta-IN'
time=translate_and_audio(text,langCode,title)
print(time)

"""# Image to Video"""

def media_to_concatenated_video(media_paths, output_path, total_duration=10, fps=24):
    """
    Convert a list of images and videos to a concatenated video using moviepy.

    Parameters:
    - media_paths (list): List of image and video file paths.
    - output_path (str): Output video file path.
    - total_duration (int): Desired total video duration in seconds.
    - fps (int): Frames per second for the output video.
    """
    # Create the output directory if it doesn't exist
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Separate the list into images and videos
    image_paths = [path for path in media_paths if path.lower().endswith(('.png', '.jpg', '.jpeg'))]
    video_paths = [path for path in media_paths if path.lower().endswith(('.mp4', '.avi', '.mov'))]

    # Convert videos to individual clips with full duration
    video_clips = [VideoFileClip(video_path) for video_path in video_paths]

    # Calculate the remaining duration for images
    remaining_duration = total_duration - sum([clip.duration for clip in video_clips])

    # Convert images to individual clips with adjusted duration
    image_clips = []
    if image_paths:
        image_duration = remaining_duration / len(image_paths)
        for image_path in image_paths:
            img = ImageSequenceClip([image_path], fps=fps)
            img = img.set_duration(image_duration)
            image_clips.append(img)

    # Concatenate all clips (videos and images)
    final_clip = concatenate_videoclips(video_clips + image_clips, method="compose")

    # Write the concatenated video to a file
    final_clip.write_videofile(output_path, codec='libx264', fps=fps)

    # Close the video clips
    for clip in video_clips:
        clip.close()

    print(f"Concatenated video file created: {output_path}")

def overlay_audio_on_video(video_path, audio_path, output_path):
    # Load video clip
    video_clip = VideoFileClip(video_path)

    # Load audio clip
    audio_clip = AudioFileClip(audio_path)

    # Overlay audio on video
    video_clip = video_clip.set_audio(audio_clip)

    # Write the result to a new file
    video_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", temp_audiofile="temp_audio.m4a", remove_temp=True)

def check_and_delete_video(video_id, mongodb_uri, database_name, collection_name,file_name):
    # Connect to MongoDB
    client = MongoClient(mongodb_uri)
    db = client[database_name]
    fs = GridFS(db, collection=collection_name)

    # Check if the video with the given ID exists
    if fs.exists(ObjectId(video_id)):
        # os.remove(f'output/{file_name}.mp4')
        # os.remove(f'output/{file_name}.mp3')
        print(f'Video with ID {video_id} added from MongoDB')
        client.close()
        return True
    else:
        print(f'Video with ID {video_id} not found in MongoDB')
        client.close()
        return False

def generate_result(title,article,user_id,media_list,langCode):
    try:

            # Convert the text to audio
            audio_duration_ms = translate_and_audio(article,langCode,title)
            print(audio_duration_ms)

            # # Create a video from the images

            output_path = os.path.join(os.getcwd(), 'output', title + '.mp4')
            print(output_path)
            media_to_concatenated_video(media_list, output_path, total_duration=audio_duration_ms)


            # Add the audio to the video
            video_path = os.path.join(os.getcwd(), 'output', title + '.mp4')
            audio_path = os.path.join(os.getcwd(), '', title + '.mp3')
            output_path = os.path.join(os.getcwd(), 'output', title + '_final.mp4')
            overlay_audio_on_video(video_path, audio_path, output_path)

            # Convert the video to base64 and send it to mongo
            video_id = convert_and_upload_video(output_path, 'mongodb+srv://abinav:7RK22ZlEesfW8lyL@cluster0.7r4wtvv.mongodb.net/', 'test', 'videos', title,'655bc6f5d4064a0206af4abd')



    except Exception as e:
        return {'error': str(e)}

title = "Uttarkashi Tunnel Collapse"

article = """
Uttarkashi Tunnel Collapse: In Uttarakhand, the Silkyara tunnel collapsed on November 12, trapping around 41 men. A rescue operation for these trapped workers was put on hold on November 19 as the agencies were involved in preparing for the next stage by adopting multiple approaches to reach the men trapped for the past few days. Stay tuned for Uttarkashi Tunnel Collapse LIVE News Updates only at LiveMint.


"""
#extra content
'''
In order to rescue the 41 trapped men, Tehri Hydroelectric Development Corporation was going to start 'micro tunneling' on Sunday night on the Char Dham route from the Barkot end of the under-construction tunnel. On November 17, an American-made heavy-duty auger machine encountered a hard obstacle while boring for about 22 metres through the collapsed debris of 60-metre stretch from the Silkyara end. The boring through the debris has for now been halted.
A series of alternative rescue plans to reach the workers trapped inside the under-construction tunnel are being worked upon. According to officials, a road to the top of the hill has been laid to dig a vertical shaft into the tunnel. Union Road Transport Minister Nitin Gadkari on Sunday said a breakthrough is expected in two and a half days.
The built-up portion of the tunnel is about two kilometres and is 8.5 metres high with availability of water and electricity. So far, a 6-inch wide tube has been pushed 39 metres deep into the rubble that would send food and water to the trapped men once it cuts through completely.

After reviewing the accident site, foreign tunnel expert Arnold Dix said that the the rescue team is doing a lot of work for the safety of trapped workers. He also underlined that enormous amount of work has been done in preparation before the execution of plan.
"I only arrived yesterday but the work I have seen even between yesterday and today is extraordinary... Plan for today is working out the best thing to do to get the men out," Dix said.
However, the tunnel expert abstained from giving a timeline for the rescue opertion and said that the team is trying hard to bring out the trapped men safe and alive. '''


userid = '655bc6f5d4064a0206af4abd'

media_list = ["/content/img1.jpeg", "/content/img2.jpeg", "/content/img3.png"]

langcode = "ta-IN"

generate_result(title, article, userid, media_list, langcode)