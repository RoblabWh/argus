from detection_server import DetectionServer

def main():
    server = DetectionServer("0.0.0.0", 6000)
    server.run()


if __name__ == '__main__':
    main()