#!/usr/bin/env python3

import base64
import os
import re
import requests
import shlex
import time
from logging import getLogger, NullHandler
from lxml import etree as LET
from subprocess import DEVNULL, Popen, PIPE

from function import Function
Func = Function(logger=getLogger("docker-radio"))

# general config
from setting.general_config import *


class RadikoHLS:

    auth_key = "bcd151073c03b352e1ef2fd66c32209da9ca0afa"
    auth_token = ""
    partialkey = ""

    def __init__(self, logger=None):
        default_logger = getLogger(__name__)
        default_logger.addHandler(NullHandler)
        self.logger = logger or default_logger

    def access_auth(self):  # old: auth_by_html5_api(self)
        if self.access_auth1() is False:
            self.logger.error("auth1 response failed")
            return False

        if self.access_auth2() is False:
            self.logger.error("auth2 response failed")
            return False

        return

    def access_auth1(self):
        url = "https://radiko.jp/v2/api/auth1"
        headers = {
            "User-Agent": Func.user_agent,
            "Accept": "*/*",
            "X-Radiko-App": "pc_html5",
            "X-Radiko-App-Version": "0.0.1",
            "X-Radiko-User": "dummy_user",
            "X-Radiko-Device": "pc",
        }
        res = Func.make_request(url, headers=headers)
        if res is False:
            return False

        self.access_partial_key(res)

        return

    def access_partial_key(self, auth1_res):
        self.auth_token = auth1_res.headers["X-RADIKO-AUTHTOKEN"]
        offset = int(auth1_res.headers["X-Radiko-KeyOffset"])
        length = int(auth1_res.headers["X-Radiko-KeyLength"])

        partialkey = self.auth_key[offset: offset + length]
        self.partialkey = base64.b64encode(partialkey.encode("utf-8"))

        self.logger.debug(f"authtoken : {self.auth_token}")
        self.logger.debug(f"offset    : {offset}")
        self.logger.debug(f"length    : {length}")
        self.logger.debug(f"partialkey: {self.partialkey}")

        return

    def access_auth2(self):
        url = "https://radiko.jp/v2/api/auth2"
        headers = {
            "X-Radiko-AuthToken": self.auth_token,
            "X-Radiko-Partialkey": self.partialkey,
            "X-Radiko-User": "dummy_user",
            "X-Radiko-Device": "pc"  # "pc" 固定
        }
        res = Func.make_request(url, headers=headers)
        if res is False:
            return False

        self.area = res.content.decode("utf-8")
        self.logger.info(f"your area: {self.area}")

        return

    # select station is in area
    def is_station_available(self, station):
        stations = self.get_stations()
        if stations is False:
            self.logger.error("get list of stations failed")
            return False

        self.logger.info("--------------------------")
        self.logger.info(f" your choice : {station}")
        self.logger.info("--------------------------")

        if not station in stations:
            self.logger.error("list of stations")
            self.logger.error(f"{stations}")
            self.logger.error("--------------------------")
            self.logger.error(f"station {station} is not available.")
            return False

        return

    def get_stations(self):
        if self.get_area_id() is False:
            self.logger.error("get area id failed")
            return False

        url = f"http://radiko.jp/v3/program/now/{self.area_id}.xml"
        res = Func.make_request(url)
        if res is False:
            return False

        root = LET.fromstring(res.content)
        stations = [e.attrib["id"] for e in root.findall(".//station[@id]")]

        self.logger.info("--------------------------")
        self.logger.info(f"area id :{self.area_id}")
        self.logger.info("--------------------------")
        self.logger.info("list of now onair stations")
        self.logger.info(stations)

        return stations

    # get area
    def get_area_id(self):
        self.area_id = self.area.strip().split(",")[0]
        if self.area_id == "":
            return False

        return True

    def radiko_live_url(self, station):
        base_url = "http://f-radiko.smartstream.ne.jp"
        part_url = "_definst_/simul-stream.stream/playlist.m3u8"
        url = f"{base_url}/{station}/{part_url}"

        return url

    def chunk_m3u8_url(self, url):
        headers = {"X-Radiko-AuthToken": self.auth_token}
        res = Func.make_request(url, headers=headers)
        if res is False:
            return False

        body = res.content.decode("utf-8")
        lines = re.findall("^https?://.+m3u8$", body, flags=(re.MULTILINE))[0]
        self.logger.info(f"body: {body}")

        return lines


    # コマンドからのインターフェース
    # radiko サイマルストリームを再生する
    def play_radio(self, station, area_id, format="MP3", volume=5, duration=None):
        self.logger.info(f"Selected station : {station}")

        if self.access_auth() is False:  # update auth_token
            return False
        if self.is_station_available(station) is False:
            return False

        live_url = self.radiko_live_url(station)
        chunk_url = self.chunk_m3u8_url(live_url)
        if chunk_url is False:
            self.logger.error("live url was not found")
            return False

        Func.get_program_info(area_id, station, 0)
        self.start_time = Func.start_time
        self.end_time = Func.end_time

        if Func.station_name != "":
            station_name = Func.station_name
        else:
            station_name = f" [{station}/{area_id}]"
        self.logger.debug(f"station_name2: {station_name}")

        if Func.update_ezstream_config(format, station_name) is False:
            return False

        player_cmd = Func.play_cmd(chunk_url, format, volume, duration)
        cast_cmd = f"ezstream -c /ezstream/ezstream-radio_{format}.xml"
        if EZ_DEBUG is True:
            cast_cmd = f"ezstream -vvv -c /ezstream/ezstream-radio_{format}.xml"
        self.logger.debug(f"player_cmd: {player_cmd}")
        self.logger.debug(f"cast_cmd: {cast_cmd}")

        self.p1 = Popen(
            shlex.split(player_cmd), stdout=PIPE, stderr=DEVNULL
        )

        time.sleep(0.1)
        p1_count = 0
        while True:
            self.logger.debug(f"returncode: p1= {self.p1.poll()}")
            if self.p1.returncode is None:
                break
            else:
                self.logger.debug("p1 not work!")
                p1_count += 1
                time.sleep(0.2)
                if p1_count == 5:
                    self.logger.debug("p1 not work give up!")
                    break
        if EZ_DEBUG is True:
            self.p2 = Popen(
                shlex.split(cast_cmd), stdin=self.p1.stdout, stdout=PIPE, stderr=PIPE
            )
        else:
            self.p2 = Popen(
                shlex.split(cast_cmd), stdin=self.p1.stdout, stdout=DEVNULL, stderr=DEVNULL
            )

        self.logger.info("Radiko playback start")

        return
