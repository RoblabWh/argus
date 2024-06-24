import os
from detection_server import DetectionServer

def main():
    device = "cpu"
    if os.getenv("ARGUS_GPU_NVIDIA", "false") == "true":
        device = "cuda:0"

    server = DetectionServer("0.0.0.0", 6000, device)
    server.run()


if __name__ == '__main__':
    main()
