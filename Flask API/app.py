from flask import Flask, request, jsonify
from flask_restx import Api
from pydub import AudioSegment
from pymongo import MongoClient, PyMongo
from gridfs import GridFS
from bson import ObjectId
from moviepy.editor import VideoFileClip, AudioFileClip, ImageSequenceClip, concatenate_videoclips
from google.cloud import texttospeech
from google.cloud import translate_v2 as translate
import os
import base64

#ffmpeg imports
ffmpeg_path = "/Users/anandkumarns/Downloads/ffmpeg"
ffprobe_path = "/Users/anandkumarns/Downloads/ffmpeg/ffprobe"
#gcp imports

# Set the paths for ffmpeg and ffprobe
AudioSegment.converter = ffmpeg_path
AudioSegment.ffmpeg = ffmpeg_path
AudioSegment.ffprobe = ffprobe_path
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/content/speedy-lattice-405709-70ec37c10a13.json"

app = Flask(__name__)
api = Api(app)

# Rest of the code remains the same...


def overlay_audio_on_video(video_path, audio_path, output_path):
    # Load video clip
    video_clip = VideoFileClip(video_path)

    # Load audio clip
    audio_clip = AudioFileClip(audio_path)

    # Overlay audio on video
    video_clip = video_clip.set_audio(audio_clip)

    # Write the result to a new file
    video_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", temp_audiofile="temp_audio.m4a", remove_temp=True)


def translate_text(target: str, text: str) -> dict:
    translate_client = translate.Client()
    if isinstance(text, bytes):
        text = text.decode("utf-8")

    result = translate_client.translate(text, target_language=target)

    print("Text: {}".format(result["input"]))
    print("Translation: {}".format(result["translatedText"]))
    print("Detected source language: {}".format(result["detectedSourceLanguage"]))

    return result["translatedText"]

def check_and_delete_video(video_id, mongodb_uri, database_name, collection_name,file_name):
    # Connect to MongoDB
    client = MongoClient(mongodb_uri)
    db = client[database_name]
    fs = GridFS(db, collection=collection_name)

    # Check if the video with the given ID exists
    if fs.exists(ObjectId(video_id)):
        os.remove(f'output/{file_name}.mp4')
        os.remove(f'output/{file_name}.mp3')
        print(f'Video with ID {video_id} deleted from MongoDB')
        client.close()
        return True
    else:
        print(f'Video with ID {video_id} not found in MongoDB')
        client.close()
        return False

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





def tts(article, langCode, title):
    client = texttospeech.TextToSpeechClient()
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

    # Construct the file path
    mp3_path = os.path.join(os.getcwd(), 'output', title + '.mp3')

    try:
        with open(mp3_path, 'wb') as mp3_file:
            mp3_file.write(bytes(response.audio_content))
        print(f"MP3 file successfully written to {mp3_path}")

        audio = AudioSegment.from_mp3(mp3_path)
        audio_duration_ms = len(audio) / 1000

        return audio_duration_ms

    except Exception as e:
        print(f"Error: {e}")
        return None


def translate_and_audio(text,langCode,title):
  translated=translate_text(langCode[0:2],text)
  return tts(translated,langCode,title)


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



@api.route('/online', methods=['GET'])
def online():
    return {'status': 'online'}


@api.route('/generate_result', methods=['POST'])
def generate_result():
    try:
            data = request.get_json()

            # Extract data from the JSON payload
            title = data.get('title')
            article = data.get('article')
            user_id = data.get('user_id')
            media_list = data.get('media_list', [])
            langCode = data.get('langCode')

            # Convert the text to audio
            audio_duration_ms = translate_and_audio(article,langCode,title)

            # Create a video from the images

            output_path = os.path.join(os.getcwd(), 'output', title + '.mp4')
            media_to_concatenated_video(media_list, output_path, total_duration=audio_duration_ms/1000)


            # Add the audio to the video
            video_path = os.path.join(os.getcwd(), 'output', title + '.mp4')
            audio_path = os.path.join(os.getcwd(), 'output', title + '.mp3')
            output_path = os.path.join(os.getcwd(), 'output', title + '_final.mp4')
            overlay_audio_on_video(video_path, audio_path, output_path)

            # Convert the video to base64 and send it to mongo
            video_id = convert_and_upload_video(output_path, 'mongodb://localhost:27017', 'test', 'fs.files', title)

            #check if it is saved
            check_and_delete_video(video_id, 'mongodb://localhost:27017', 'test', 'videos', title)






    except Exception as e:
        return {'error': str(e)}

@api.route('/get_video_base64', methods=['GET'])
def get_video_base64():
    mongo=PyMongo(app)
    vid_id= request.args.get('video_ID', ' ')
    collection="videos"
    video = mongo.db.your_collection.find_one({"_id": vid_id})
    if video:
        # Assuming the video is stored as a binary field in the 'data' key
        video_data = video.get("data", b"")
        video_base64 = base64.b64encode(video_data).decode("utf-8")
        return jsonify({"video_base64": video_base64})

    return jsonify({"error": "Video not found"}), 404



if __name__ == '__main__':
    app.run(debug=True)