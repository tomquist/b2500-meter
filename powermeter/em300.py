from .base import Powermeter
import requests
import time
import json

class Em300(Powermeter):
    def __init__(self, ip: str, user: str, password:str, json_power_calculate: bool):
        self.ip = ip
        self.user = user
        self.password = password
        self.json_power_calculate = json_power_calculate
        self.session = requests.Session()

    def get_json(self, path):
        import requests
        import json

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; "}
        myparams= {'login': self.user, 'password': self.password, 'save_login': '1'}
        global mySession

        try:
            mySession.get('http://'+ self.ip +'/mum-webservice/data.php',  headers=headers)
        except:
            mySession = requests.Session()
            r=mySession.get('http://'+ self.ip + '/start.php', headers=headers)
            if self.user != '':
                time.sleep(0.25)
                mySession.post('http://'+ self.ip + '/start.php', myparams, headers=headers)
            r=mySession.get('http://'+ self.ip +'/mum-webservice/data.php',  headers=headers)
        
        em300data = json.loads(r.text)

        return (em300data)    

    def get_powermeter_watts(self):
        response = self.get_json(self)
        if not self.json_power_calculate:
            return [int(response["1-0:1.4.0*255"])]
        else:
            power_in = response["1-0:1.4.0*255"]
            power_out = response["1-0:2.4.0*255"]
            return [int(power_in) - int(power_out)]
