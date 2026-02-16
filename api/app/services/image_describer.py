
import os
import logging
import base64
import redis
from pathlib import Path
from app.services.celery_app import celery_app
from PIL import Image, ImageOps
from io import BytesIO
from langchain_ollama import OllamaLLM
from exiftool import ExifToolHelper
from app.database import get_db
from app.models import Report, Image as ImageModel  
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from sqlalchemy.orm import Session
import http.client
import http
import json

import app.crud.report as report_crud
import app.crud.images as images_crud

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
UPLOAD_DIR = Path("reports_data")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_URL = f"argusII_ollama:{OLLAMA_PORT}"  
IMAGE_MODEL = "llava:v1.6"
TEXT_MODEL = "llama3.2"

NUMBER_OF_KEYWORDS = 5
MAX_DESCRIPTION_LENGTH = 180  # in characters
MAX_FINAL_DESCRIPTION_LENGTH = 500  # in characters

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)


@celery_app.task(name="description.describe_images")
def describe_images(report_id: int):
    set_redis_progress(report_id,1.0)
    try:
        if pull_model(OLLAMA_URL, IMAGE_MODEL):
            logger.info(f"First model ({IMAGE_MODEL}) loaded. Proceeding to second...")
            if pull_model(OLLAMA_URL, TEXT_MODEL):
                logger.info(f"Second model ({TEXT_MODEL}) loaded successfully.")

        data, report = load_images(report_id)
        logger.info(f"Loaded {len(data)} images for description in report {report_id}")
        
        set_redis_progress(report_id, 10.0)

        # TODO before make sure models are loaded in ollama

        prompt_report_context = f"You help in civil protection by analyzing reconnaissance data taken by UAVs in firefighting, first responder and rescue missions. \
             You analyze a number of images one after another, from a UAV flight at {report.mapping_report.address}. Focused on possible hazards, dangers and points of interest for first responders."
        # prompt_report_context = f"You are a photographer and image analyst working for a newspaper writing an ongoing civil protection mission (like firefighters, first responders, technical units...). Now you look at the images taken by UAVs at a mission at {report.mapping_report.address}."

        descriptions, headings = describe_all_images(data, prompt_report_context, report_id)
        set_redis_progress(report_id, 75.0)

        final_report = summarize_descriptions(descriptions, prompt_report_context)
        set_redis_progress(report_id, 90.0)

        report_crud.set_auto_description(next(get_db()), report_id, final_report)

        unload_model(OLLAMA_URL, IMAGE_MODEL)
        unload_model(OLLAMA_URL, TEXT_MODEL)
        # for i, img in enumerate(data):
        #     try:
        #         img_path = img.url
        #         write_metadata(img_path, descriptions[i], headings[i], headings[i])
        #     except Exception as e:
        #         logger.error(f"Failed to write metadata for image {img.id}: {e}")
        #         continue
        set_redis_progress(report_id, 100.0)
    except Exception as e:
        unload_model(OLLAMA_URL, IMAGE_MODEL)
        unload_model(OLLAMA_URL, TEXT_MODEL)
        logger.error(f"Error in description process for report {report_id}: {e}")
        set_redis_progress(report_id, -1.0)


def set_redis_progress(report_id: int, progress: float):
    status = "processing" if progress < 100.0 and progress >= 0.0 else "completed" if progress >= 100.0 else "error"
    if progress < 0.0:
        progress = 100.0

    r.set(f"description:{report_id}:progress", progress)
    r.set(f"description:{report_id}:status", status)
    return


def pull_model(address, model):
    if address is None:
        logger.error("No server address found, cannot pull model")
        return False
    else:
        logger.info(f"Pulling model {model} from server at {address}")

    conn = http.client.HTTPConnection(address, timeout=120)

    try:
        body = {"model": model}
        conn.request("POST", "/api/pull", body=json.dumps(body))
        res = conn.getresponse().read().decode("utf-8")
    except:
        logger.error("Server not reachable")
        return False
    else:
        logger.info(f"Response: {res}")
        if "\"status\":\"success\"" in res:
            logger.info("Model pulled successfully")
            return True

    logger.error(f"Model pull failed: {res}")
    return False

def unload_model(address, model):
    if address is None:
        logger.error("No server address found, cannot unload model")
        return False
    else:
        logger.info(f"Unloading model {model} from server at {address}")

    conn = http.client.HTTPConnection(address, timeout=120)

    try:
        body = {"model": model,
                "keep_alive": 0}
        conn.request("POST", "/api/generate", body=json.dumps(body))
        res = conn.getresponse().read().decode("utf-8")
    except:
        logger.error("Server not reachable")
        return False
    else:
        logger.info(f"Response: {res}")
        return True

    logger.error(f"Model unload failed: {res}")
    return False
    

def load_images(report_id: int):
    db = next(get_db())
    report = report_crud.get_basic_report(db, report_id)
    images = images_crud.get_by_report_full(db, report_id)
    images_selection = [img for img in images if not img.thermal and not img.panoramic]

    if not images_selection or len(images_selection) == 0:
        raise ValueError("No suitable images found for description") # alternatively just return and finish task

    return images_selection, report

def describe_all_images(data, prompt_report_context: str, report_id: int):

    prompt_heading = f"{prompt_report_context} Describe this image with a heading, that sums up what is happening in the image in a few words."
    prompt_keywords = f"{prompt_report_context} Extract {NUMBER_OF_KEYWORDS} relevant keywords that describe the main elements in the image."
    prompt_description = f"{prompt_report_context} Generate a short and informative description of the image in no more than {MAX_DESCRIPTION_LENGTH} characters and only describe what had been seen in the images. \
        No need for headings or formatting. If there is nothing interesting to see, say so and write only a short sentence about the general area depicted within the image."
    prompt_description_minimalPrompt = f"Describe the image taken from a drone in no more than {MAX_DESCRIPTION_LENGTH} characters."

    descriptions = []
    headings = []

    llm_inst = OllamaLLM(model=IMAGE_MODEL, base_url=f"http://{OLLAMA_URL}/", temperature=0)

    logging.info(f"Uploading images from {UPLOAD_DIR}...")

    for i, img in enumerate(data):
        # load image
        img_path = img.url
        if not os.path.exists(img_path) or not img_path.endswith(('.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG')):
            
            logging.warning(f"Image path {img_path} does not exist or is not a valid image file.")
            continue
        try:
            image = Image.open(img_path)
        except Exception as e:
            logging.error(f"Failed to open image {img_path}: {e}")
            continue
        
        detections_summary = summarize_detections(img)
        # logger.info(f" Timestamp: {img.created_at}, (with type {type(img.created_at)}) Detections: {detections_summary}")
        prompt_image_context = f"The image was taken at {img.created_at}.{detections_summary}"

        ImageOps.exif_transpose(image, in_place=True)
        image.thumbnail((672, 672))
        image_b64 = convert2Base64(image)
        llm_context = llm_inst.bind(images=[image_b64])

        def call_llm(prompt):
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(llm_context.invoke, prompt)
                try:
                    return future.result(timeout=1800.0).strip()
                except TimeoutError:
                    logging.error("Timeout while waiting for LLM")
                    return ""
                except Exception as e:
                    logging.error(f"Error during LLM invocation: {e}")
                    return ""
                

        description = call_llm(f"{prompt_description} {prompt_image_context} ")
        descriptions.append(description)

        # keyword_text = call_llm(f"{prompt_keywords} {prompt_image_context} ")
        # if keyword_text:
        #     keywords = [line.lstrip("0123456789. ").strip() for line in keyword_text.splitlines() if
        #                 line.strip()]
        # else:
        #     keywords = []
        # logging.info(f"Keywords: {keywords}")

        # heading = call_llm(f"{prompt_heading} {prompt_image_context} ")
        # logging.info(f"Heading: {heading}") 
        # headings.append(heading)

        set_redis_progress(report_id, 10.0 + (i / len(data)) * 65.0)

    return descriptions, headings

def summarize_descriptions(descriptions, prompt_report_context, translate_to='german'):
    summary_llm = OllamaLLM(model=TEXT_MODEL, base_url=f"http://{OLLAMA_URL}/", temperature=0)

    full_report_prompt = f"{prompt_report_context}. There are {len(descriptions)} images of partially overlapping images to summarize. \
        Each Image already has a short description. \
        Summarize the following image descriptions into a concise report, highlighting key observations and relevant details. \
        Keep it under {MAX_FINAL_DESCRIPTION_LENGTH} characters and leave unnecessary details out.\n \
        Here are the descriptions:\n\n"
    
    for i, desc in enumerate(descriptions):
        full_report_prompt += f"Image {i+1}: {descriptions[i]}. {desc}\n"

    full_report_prompt += "\nEnd of descriptions.\n\nPlease provide the full summary without any special formatting. No need for conversation and introductions, just report the facts."

    final_report = summary_llm.invoke(full_report_prompt).strip()

    if (translate_to):
        final_report = translate_text(final_report, target_language=translate_to)

    return final_report

def summarize_detections(image: ImageModel):
    if not image.detections or len(image.detections) == 0:
        return " "
    
    summary = {}
    for det in image.detections:
        name = det.class_name
        if name in summary:
            summary[name] += 1
        else:
            summary[name] = 1

    summary_parts = [f"{count} {name}(s)" for name, count in summary.items()]
    return " An AI model detected the following objects in this image: " + ", ".join(summary_parts)

def translate_text(text: str, target_language: str):
    translation_llm = OllamaLLM(model=TEXT_MODEL, base_url=f"http://{OLLAMA_URL}/", temperature=0)

    translation_prompt = f"Translate the following text to {target_language} while keeping the meaning intact. Do not change any names or addresses. Keep it concise and clear, do not use special formatting.\n\nText: {text}\n\nTranslated Text:"

    translated_text = translation_llm.invoke(translation_prompt).strip()
    return translated_text


def convert2Base64(image):
    buffered = BytesIO()
    rgb_im = image.convert('RGB')
    rgb_im.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str

def write_metadata(filename, abstract, keywords, headline=None):
    logger.info(f"Writing {keywords} to {filename}")
    tags = {"IPTC:Writer-Editor": IMAGE_MODEL,
            "IPTC:Caption-Abstract": abstract,
            "EXIF:UserComment": abstract,
            "IPTC:Keywords": keywords,}
    if headline is not None:
        tags["IPTC:Headline"] = headline
        tags["EXIF:ImageDescription"] = headline
    with ExifToolHelper() as et:
        et.set_tags(filename,
            tags=tags
            )
    return


def start_description_process(report_id: int, db: Session):
    report = report_crud.get_basic_report(db, report_id)
    if not report:
        raise ValueError("Report not found")
    
    #check if redis has a task running
    existing_task_id = r.get(f"description:{report_id}:task_id")
    if existing_task_id:
        progress = r.get(f"description:{report_id}:progress")
        status = r.get(f"description:{report_id}:status")
        if status in [b"processing", b"queued"]:
            raise ValueError("Description process already running for this report")
        if progress and float(progress) < 100.0:
            raise ValueError("Description process already running for this report")
        #start new task

    task = describe_images.delay(report_id)
    r.set(f"description:{report_id}:status", "queued")
    r.set(f"description:{report_id}:progress", 0.0)
    r.set(f"description:{report_id}:task_id", task.id)
    return {"status": "started", "task_id": task.id}