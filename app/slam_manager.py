import requests

class SlamManager:

    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.url = 'http://' + this.address + ':' + str(self.port)

    def  start_slam(self, report_id, video, config, orb_vocab, slam_options):

        data= {'report_id': report_id,
               'video': video,
               'orb_vocab': orb_vocab,
               'config': config,
               'slam_options': slam_options}

        requests.post(self.url+'/slam', json=data)
        return True

    def get_slam_status(self, report_id):
        response = requests.get(self.url+'/get_slam_status', headers={'Accept': 'application/json'})
        return "running"