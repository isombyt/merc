#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
from CryptUtils import auth, Account
import json
import hashlib
import random
import urllib
import urlparse
import zlib
import time
import traceback
from gevent.coros import BoundedSemaphore
loginLock = BoundedSemaphore(100)
mlkLock = BoundedSemaphore(200)

proxies = {"http": "http://127.0.0.1:8888"}
proxies = None

def calcDeviceID(username):
    return hashlib.md5(username).hexdigest()[8:24]

def randomDeviceID():
    table = "0123456789abcdef"
    return "".join([random.choice(table) for i in range(16)])

class HEAuth(object):
    baseUrl = "http://account.miracle.happyelements.cn/account?uid=666666"

    headers = {
        "Content-Encoding": "deflate",
        "Accept-Encoding": "deflate",
        "DEVICE_INFO": "Sony SOL21:::Android OS 4.1.2 / API-16 (9.1.D.0.401/bj5_tw)",
        "Device": "android",
        "Content-Type": "application/octet-stream",
        "AppVersion": "29",
        "Accept": "application/octet-stream",
        "User-Agent": "Dalvik/1.6.0 (Linux; U; Android 4.1.2; SOL21 Build/9.1.D.0.401)",
    }
    
    def __init__(self):
        self._st = -1
        self.sk = "gip-eurhieur8387583979385798327958udfhdjf"
        self._head = {
            'lang': 'zh_CN',
            'st': 0,
            'sk': self.sk,
            'mv': '1',
            'pf': 'Android',
            'notify': False,
            'uk': '',
            'v': '1',
            'aid': '11',
            'ct': 0
        }

    @property
    def json_header(self):
        self._head["st"] = self.st
        self._head["sk"] = self.sk
        return self._head

    def _post(self, data):
        try:
            body = [self.json_header, data if isinstance(data, list) else [data]]
            data = auth.encrypt(json.dumps(body))
            loginLock.acquire()
            ret = requests.post(self.baseUrl, headers=self.headers, data=data, proxies=proxies)
        except:
            pass
        finally:
            loginLock.release()
        return auth.decrypt(ret.content)

    def action(self, method, **argv):
        argv["method"] = method
        data = self._post(argv)
        return json.loads(data)

    @property
    def st(self):
        self._st += 1
        return self._st

    def actions(self, actions):
        return json.loads(self._post(actions))

    def UsernameAviable(self, username):
        data = self.action("heRegCheck",accountName=username)
        results = data["results"]
        for result in results:
            return result["ok"]

    def setUserInfo(self, deviceID, accountID, token):
        self.deviceID = deviceID
        self.accountID = accountID
        self.token = token

    def QuickStart(self):
        self.deviceID = randomDeviceID()
        randomStr = str(random.randint(100000000,999999999))
        ret = self.action("heQuickLogin", randomStr=randomStr, deviceId=self.deviceID)
        for result in ret["results"]:
            if result["success"]:
                self.accountID = result["heAccountId"]
                self.token = result["token"]
                return True
        return False

    def Regist(self, username, password):
        self.deviceID = calcDeviceID(username)
        ret = self.action("heRegister", accountName=username, pwd=password, deviceId=self.deviceID)
        results = ret["results"]
        for result in results:
            if result["success"]:
                self.accountID = result["heAccountId"]
                self.token = result["token"]
                return True
        return False

    def Login(self, username, password):
        self.deviceID = calcDeviceID(username)
        ret = self.action("heLogin", userName=username, pwd=password, deviceId=self.deviceID)
        results = ret["results"]
        for result in results:
            if result["success"]:
                self.accountID = result["heAccountId"]
                self.token = result["token"]
                return True
        return False

    def GetServerList(self):
        ret = self.action("getServerList", token=self.token,
            deviceId=self.deviceID, heAccountId=self.accountID,
            clientVersion=20)
        results = ret["results"]
        for result in results:
            return result

    def ChooseServer(self, serverID):
        ret = self.action("chooseServer", heAccountId=self.accountID,
            token=self.token, serverId=serverID, deviceId=self.deviceID)
        results = ret["results"]
        for result in results:
            self.sk = result["sk"]
            self.userID = result["userId"]
            return result

    def BindAccount(self, username, password, userID, token):
        self.deviceID = calcDeviceID(username)
        ret = self.action("heAccountBind", accountName=username, pwd=password, deviceId=self.deviceID)
        return ret

class KYAuth(object):

    def __init__(self):
        pass

class LibMLK(object):

    def __init__(self, serverIP, he):
        self.serverIP = serverIP
        self.baseUrl = "http://%s/"%serverIP
        self.userID = he.userID
        self.sk = he.sk
        self.crypt = Account(self.userID, self.sk)

    @property
    def headers(self):
        return {
            "APP_ID_4": self.crypt.cryptedSessionKey,
            "APP_ID_2": self.crypt.hashedUserID,
            "APP_ID_1": self.crypt.cryptedUserID,
            "Encrypted": True,
            "DEVICE_INFO": "Sony SOL21:::Android OS 4.1.2 / API-16 (9.1.D.0.401/bj5_tw)",
            "Device": "android",
            "AppVersion": 29,
            "Accept": "application/json",
            "User-Agent": "Dalvik/1.6.0 (Linux; U; Android 4.1.2; SOL21 Build/9.1.D.0.401)"
        }

    def _post(self, url, params={}, data={}):
        data["_method"] = "GET"
        data = urllib.urlencode(data)
        data = self.crypt.encrypt(data)
        url = urlparse.urljoin(self.baseUrl, url)
        if len(params) > 0:
            e = self.crypt.encrypt(urllib.urlencode(params)).encode("base64").replace("\n","")
            url = "%s?e=%s"%(url,e)
        ret = None
        try:
            mlkLock.acquire()
            ret = requests.post(url, data=data, headers=self.headers, proxies=proxies)
        except:
            traceback.print_exc()
        finally:
            mlkLock.release()
        if ret is None:
            raise BaseException()
        if "encrypted" in ret.headers and ret.headers["encrypted"] == "true":
            rtn = self.crypt.decrypt(ret.content)
        try:
            rtn = zlib.decompress(rtn)
        except:
            print "try to decpmpress failed"
        return rtn

    def get(self, url, params={}, data={}):
        url = urlparse.urlparse(url)
        path = url.path
        query = dict(urlparse.parse_qsl(url.query))
        query.update(params)
        return self._post(path, params=query, data=data)

    def setUsername(self, name):
        ret = self._post("users/update", data={"user_name":name})
        self.user_name = name
        return json.loads(ret)

    def finishTutorial(self):
        ret = self._post("users/update",
            data={"user_name": self.user_name, "tutorial_finish": True})
        return json.loads(ret)

    def getMessages(self, page_type="Home"):
        params = {
            "last_read_at": int(time.time()),
            "page_type": page_type
        }
        ret = self._post("users/messages", params=params)
        return json.loads(ret)

    def getStages(self):
        ret = self._post("stages")
        return json.loads(ret)

    def getAreas(self, stage_id):
        ret = self._post("areas", params={"stage_id": stage_id})
        return json.loads(ret)

    def getMonsters(self):
        ret = self._post("user_monsters")
        return json.loads(ret)

    def getDecks(self):
        ret = self._post("user_decks")
        return json.loads(ret)

    def getUnits(self):
        ret = self._post("user_units")
        return json.loads(ret)

    def receiveLoginBonus(self):
        ret = self._post("users/receive_login_bonus")
        return json.loads(ret)

    def getLoginRewardList(self):
        ret = self._post("accu_login_activity")
        return json.loads(ret)

    def receiveLoginReward(self, day):
        params={"day":day}
        ret = self._post("accu_login_activity/fetch_rewards", params=params)
        return json.loads(ret)

    def getRewardList(self):
        ret = self._post("user_presents")
        return json.loads(ret)

    def reward(self, uuid):
        params = {"uuid": uuid}
        ret = self._post("user_presents/receive", params)
        return json.loads(ret)

    def rewardAll(self):
        ret = self._post("user_presents/receive")
        return json.loads(ret)

    def getUserData(self):
        ret = self._post("users/preset_data.json")
        return json.loads(ret)

    def gacha(self, gacha_id, num):
        params = {"id":gacha_id, "count": num}
        ret = self._post("gachas/execute", params=params)
        return json.loads(ret)

    def getUnitList(self):
        ret = self._post("user_units")
        return json.loads(ret)

    def quest(self, quest_id, party_id="001", difficulty_id="normal"):
        params = {
            "base": "Quest/Quest",
            "difficulty_id": difficulty_id,
            "id": quest_id,
            "mode": "quest",
            "name": "Quest",
            "party_id": "001",
            "tipsLoading": "true",
        }
        ret = self._post("quests/execute/%s.json"%quest_id, params=params)
        ret = json.loads(ret)
        result_url = ret["result_url"]
        if "ap_use_url" in ret:
            ap_use_url = ret["ap_use_url"]
            self.get(ap_use_url)
        time.sleep(30)
        ret = self.get(result_url, params={"time":"27.1234"})
        return ret

if __name__ == "__main__":
    he = HEAuth()
    he.QuickStart()
    he.ChooseServer("1")
    mlk = LibMLK("203.195.138.14", he)
    mlk.setUsername("nickname")
    mlk.finishTutorial()
    print json.loads(mlk.get("/users/preset_data.json"))["data"]["user"]["level"]
    for quest in xrange(1,9):
        mlk.quest(quest)
    rewardList = mlk.getRewardList()["data"]["user_presents"]
    print json.dumps(rewardList)
    print json.loads(mlk.get("/users/preset_data.json"))["data"]["user"]["level"]