#!/usr/bin/env python3

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


class RadiruHLS:

    stations_url = "https://www.nhk.or.jp/radio/config/config_web.xml"

    def __init__(self, logger=None):
        default_logger = getLogger(__name__)
        default_logger.addHandler(NullHandler)
        self.logger = logger or default_logger

        self.list_root = self.get_xml_of_urls()
        if self.list_root is False:
            self.logger.error("get stations list failed")
            return

        self.areas = [e.text for e in self.list_root.findall(".//area")]
        self.areas_jp = [e.text for e in self.list_root.findall(".//areajp")]
        self.areas_radiko = ["JP1","JP4","JP13","JP23","JP27","JP34","JP38","JP40"]
               # areas_jp : [札幌、仙台、東京、名古屋、大阪、広島、松山、福岡]
        self.stations = ["r1hls", "r2hls", "fmhls"]
        self.stations_jp = ["NHKラジオ第1", "NHKラジオ第2", "NHK-FM"]
        self.stations_radiko = {
            "JP1": ["JOIK", "JOAB", "JOAK-FM"], "JP4": ["JOHK", "JOAB", "JOAK-FM"],
            "JP13": ["JOAK", "JOAB", "JOAK-FM"], "JP23": ["JOCK", "JOAB", "JOAK-FM"],
            "JP27": ["JOBK", "JOAB", "JOAK-FM"], "JP34": ["JOFK", "JOAB", "JOAK-FM"],
            "JP38": ["JOZK", "JOAB", "JOAK-FM"], "JP40": ["JOLK", "JOAB", "JOAK-FM"],
        }

    def get_xml_of_urls(self):
        headers = {"User-Agent": Func.user_agent}
        res = Func.make_request(self.stations_url, headers=headers)
        if res is False:
            return False

        root = LET.fromstring(res.content)

        return root

    def is_area_available(self, area):
        self.logger.info("--------------------------")
        self.logger.info(f" your choice : {area}")
        self.logger.info("--------------------------")

        if not area in self.areas:
            self.logger.error("list of areas")
            self.logger.error(f"{self.areas}")
            self.logger.error("--------------------------")
            return False

        return True

    def is_station_available(self, station):
        self.logger.info("--------------------------")
        self.logger.info(f" your choice : {station} ")
        self.logger.info("--------------------------")

        if not station in self.stations:
            self.logger.error("list of stations")
            self.logger.error(f"{self.stations}")
            self.logger.error("--------------------------")
            return False

        return True

    def chunk_m3u8_url(self, area, station):
        root = self.list_root
        url = [
            e.text for e in root.xpath(
                f"//area[text()='{area}']/following-sibling::{station}")][0]

        return url


    # コマンドからのインターフェース
    # radiru サイマルストリームを再生する
    def play_radio(self, station, area, format="MP3", volume=5, duration=None):
        self.logger.info(f"Selected station: {station}")

        if self.is_area_available(area) is False:
            self.logger.error(f"area {area} is not available.")
            return False
        if self.is_station_available(station) is False:
            self.logger.error(f"station {station} is not available.")
            return False

        chunk_url = self.chunk_m3u8_url(area, station)
        if chunk_url is False:
            self.logger.error("live url was not found")
            return False

        radiko_area = self.areas_radiko[self.areas.index(area)]
        radiko_station = self.stations_radiko[radiko_area][self.stations.index(station)]
        self.logger.debug(f"radiko_area   : {radiko_area}")
        self.logger.debug(f"radiko_station: {radiko_station}")

        Func.get_program_info(radiko_area, radiko_station, 0)
        self.start_time = Func.start_time
        self.end_time = Func.end_time

        stations_name = self.stations_jp[self.stations.index(station)]
        area_name = self.areas_jp[self.areas.index(area)]
        if Func.station_name != "":
            station_local = re.findall("(?<=\（).+?(?=\）)", Func.station_name)[0]
        else:
            station_local = "全国"
        station_name = f"{stations_name}/{area_name}[{station_local}]"
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

        self.logger.info("Radiru playback start")

        return

