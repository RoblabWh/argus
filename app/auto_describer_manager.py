import http
import http.client
import json
from threading import Thread
import threading
class ImageDescriberManager:
    def __init__(self, base_url, port=11434, model_img="llava:v1.6", model_text="llama3.2"):
        self.port = port
        self.base_url = base_url
        self.model_img = model_img
        self.model_text = model_text
        self.server_address = self._check_ollama_address(base_url, port)
        self.model_loaded = False
        self.model_loaded_lock = threading.Lock()  # Optional: for thread safety

        if self.server_address:
            # self.model_loaded = self.pull_model(self.server_address, model)
            Thread(target=self._load_model_async, daemon=True).start()

        self.threads = []

    def _load_model_async(self):
        img_loaded = self.pull_model(self.server_address, self.model_img)
        if img_loaded:
            print(f"First model ({self.model_img}) loaded. Proceeding to second...", flush=True)
            text_loaded = self.pull_model(self.server_address, self.model_text)
            if text_loaded:
                print(f"Second model ({self.model_text}) loaded successfully.", flush=True)
                with self.model_loaded_lock:
                    self.model_loaded = True
                return

        print("Failed to load one or both models.", flush=True)

    def is_model_loaded(self):
        with self.model_loaded_lock:
            return self.model_loaded

    def set_port(self, port):
        self.port = port
        self.server_address = self._check_ollama_address(self.base_url, port)

    def set_base_url(self, base_url):
        self.base_url = base_url
        self.server_address = self._check_ollama_address(self.base_url, self.port)

    def get_threads(self):
        return self.threads

    @staticmethod
    def pull_model(address, model):
        if address is None:
            print("No server address found, cannot pull model", flush=True)
            return False

        conn = http.client.HTTPConnection(address, timeout=120)
        print(conn, flush=True)

        try:
            body = {"model": model}
            conn.request("POST", "/api/pull", body=json.dumps(body))
            res = conn.getresponse().read().decode("utf-8")
            print("Response:", res, flush=True)
        except:
            print("Server not reachable", flush=True)
            return False
        else:
            print(res, flush=True)
            if "\"status\":\"success\"" in res:
                print("Model pulled successfully", flush=True)
                return True

        print("Model pull failed:", res, flush=True)
        return False


    def start_describer_for_images(self, images, report_id):
        if not self.is_model_loaded():
            print("Model not available, either wait for model download or restart container", flush=True)
            return

        self.threads.append(ImageDescriberThread(self.server_address, images, report_id, self.model_img, self.model_text))
        self.threads[-1].start()

    def get_progress(self, report_id):
        # Check for all threads with report_id if they are still running
        total = 0
        finished = 0
        done = True
        has_thread_of_report = False
        auto_description = None

        for thread in self.threads:
            if thread.report_id == report_id:
                total += thread.total
                finished += thread.finished
                has_thread_of_report = True
                if not thread.done:
                    done = False
                else:
                    auto_description = thread.auto_description


        if done and has_thread_of_report:
            self.cleanup_threads(report_id)
            print(" !!!!!! All threads finished, cleaning up and returning 1", flush=True)
            return 1, auto_description
        elif total == 0:
            if self.model_loaded:
                print(" !!!!!! No thread found for report", report_id, flush=True)
                return -1, None
            else:
                print(" !!!!!! Model not available, either wait for model download or restart container", flush=True)
                return -2, None
        else:
            print(" !! Thread still running, returning progress", flush=True)
            progress = finished / total
            if progress >= 0.99:
                progress = 0.99
            return progress, None

    def cleanup_threads(self, report_id):
        print("Cleaning up threads for report", report_id, flush=True)
        # Remove all finished threads
        threads = []
        for thread in self.threads:
            if not thread.done or thread.report_id != report_id:
                threads.append(thread)

        self.threads = threads

    def _check_ollama_address(self, url, port):
        address = url + ":" + str(port)
        print("Checking server address", address, flush=True)
        conn = http.client.HTTPConnection(url, port=port, timeout=10)
        print(conn, flush=True)
        try:
            conn.request("GET", "")
            res = conn.getresponse().read()
        except Exception as e:
            print("Server not reachable with", e, flush=True)
            #address = ""
        else:
            print("Server reachable with", res, flush=True)
        finally:
            conn.close()

        if address == "":
            return None

        return address


import os
from threading import Thread
from PIL import Image, ImageOps
import base64
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from langchain_ollama import OllamaLLM
from exiftool import ExifToolHelper


class ImageDescriberThread(Thread):
    def __init__(self, server_address, images, report_id, model_img, model_text):
        Thread.__init__(self)
        self.server_address = server_address
        self.images = images
        self.report_id = report_id
        self.done = False
        self.total = len(images)
        self.finished = 0
        self.keyword_num = 8
        self.model_img = model_img
        self.model_text = model_text
        self.auto_description = None

    def run(self):
        llm_inst = OllamaLLM(model=self.model_img, base_url="http://" + self.server_address, temperature=0)
        # prompt_headline = "You are in the role of a drone operator of a fire-brigade. Give the aerial photo a short but precise title that you can use to reference this image based on its content."
        prompt_abstract = "You are a firefighter oparating a drone. Describe what you can see within the drone image. The describtion should include the most important information, but should not be longer than two sentence. If there is nothing interesting to see, write only a short sentence about the general area depictied within the image."
        prompt_keywords = f"You are in the role of a drone operator of a fire-brigade. Find {self.keyword_num} single keywords describing and categorizing the aerial photo."

        abstracts = []

        for image_path in self.images:
            if os.path.isfile(image_path) and image_path.endswith(('.jpg', '.jpeg', '.JPG', '.JPEG')):
                print(f"Describing image {image_path} on server {self.server_address}", flush=True)
                try:
                    image = Image.open(image_path)
                except:
                    print(f"Can't load {image_path}, skipping...", flush=True)
                    continue

                ImageOps.exif_transpose(image, in_place=True)
                image.thumbnail((672, 672))
                image_b64 = self.convert2Base64(image)
                llm_context = llm_inst.bind(images=[image_b64])

                def call_llm(prompt):
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(llm_context.invoke, prompt)
                        try:
                            return future.result(timeout=1800.0).strip()
                        except TimeoutError:
                            print("Timeout while waiting for LLM")
                            return ""

                # headline = call_llm(prompt_headline)
                # print(f"Headline: {headline}")

                abstract = call_llm(prompt_abstract)
                abstracts.append(abstract)

                keyword_text = call_llm(prompt_keywords)
                if keyword_text:
                    keywords = [line.lstrip("0123456789. ").strip() for line in keyword_text.splitlines() if
                                line.strip()]
                else:
                    keywords = []
                print(f"Keywords: {keywords}")

                self.write_metadata(image_path, abstract, keywords)

            self.finished += 1

        #use all abstracts to write a general description using another ollama LLM
        # use model "llama3.2" for this
        #prompt_complete_report_summary = f"You are in the role of a drone operator of a fire-brigade. You have been taken over {len(self.images)} partially overlapping images. Each is described by one sentence, Write a short situational report describing the situation in the area. The report should be a short summary of the image content, including the most important information, in total not longer than 300 words"
        if abstracts:
            combined_abstracts = "\n".join(abstracts)
            prompt_complete_report_summary = (
                "You are in the role of a drone operator of a fire-brigade. "
                f"You have taken over {len(self.images)} partially overlapping images with a drone. "
                "Each image has a short description:\n\n"
                f"{combined_abstracts}\n\n"
                "Write a small report summarizing the overall situation in the area. with the most important findings"
                "Keep it short, not longer than 300 words and only describe what had been seen in the images. No deed for headings or specific formatting."
            )

            summary_llm = OllamaLLM(model=self.model_text, base_url="http://" + self.server_address, temperature=0)
            try:
                final_report = summary_llm(prompt_complete_report_summary).strip()
            except Exception as e:
                final_report = "Summary generation failed."
                print(f"Error generating summary: {e}", flush=True)

            print(final_report)
            self.auto_description = final_report



        self.done = True
        print(f"Finished describing images for report {self.report_id}", flush=True)

    def convert2Base64(self, image):
        buffered = BytesIO()
        rgb_im = image.convert('RGB')
        rgb_im.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return img_str

    def write_metadata(self, filename, abstract, keywords, headline=None):

        tags = {"IPTC:Writer-Editor": self.model_img,
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

