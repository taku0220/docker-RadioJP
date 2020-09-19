#!/usr/bin/env python3

import glob
import io
import os
import requests
from datetime import datetime, timedelta
from logging import getLogger, NullHandler
from lxml import etree as LET
from PIL import Image

# general config
from setting.general_config import *


class Function:

    user_agent = "curl/7.69.1"

    def __init__(self, logger=None):
        default_logger = getLogger(__name__)
        default_logger.addHandler(NullHandler)
        self.logger = logger or default_logger

    def make_request(self, url, headers="", s_code=None, stream=False):
        self.logger.debug(f"Sending GET {url} with headers: {headers}")

        try:
            res = requests.get(
                url, headers=headers, stream=stream, data=None, timeout=30
            )
        except requests.exceptions.RequestException as err:
            self.logger.error(err)
            return False

        if s_code is None:
            return res
        elif res.status_code != s_code:
            self.logger.error(f"request fail -status code:[{res.status_code} ]")
            return False
        else:
            self.logger.debug(f"Got {res.status_code} response from {url}")
            return True

    def get_program_info(self, area_id, station, when):  # when :0(now) or 1(next)
        if area_id == "":
            self.follow_pg_info(station)
            self.logger.error("area id is no value")
            return
        if station == "":
            self.follow_pg_info(station)
            self.logger.error("station id is no value")
            return

        url = f"http://radiko.jp/v3/program/now/{area_id}.xml"
        res = self.make_request(url)
        if res is False:
            self.logger.error("Radiko program url was not access")
            return

        root = LET.fromstring(res.content)
        stations = [e.attrib["id"] for e in root.findall(".//station[@id]")]
        if not station in stations:
            self.follow_pg_info(station)
            self.logger.error(f"{station} was not found in Radiko stations")
            return

        self.station_name = [
            e.text for e in root.xpath(
                f"//station[@id=\'{station}\']/name")][0]

        to_time = [
            e.attrib["to"] for e in root.xpath(
                f"//station[@id=\'{station}\']/progs/prog")]

        # if start time is passed.
        ret = datetime.strptime(to_time[when], "%Y%m%d%H%M%S")
        if when == 0 and datetime.now() >= (ret - timedelta(seconds=10)):
            self.end_time = to_time[1]
            when = 1
        else:
            self.end_time = to_time[when]

        title = [
            e.text for e in root.xpath(
                f"//station[@id=\'{station}\']/progs/prog/title")][when]
        artwork_url = [
            e.text for e in root.xpath(
                f"//station[@id=\'{station}\']/progs/prog/img")][when]
        self.start_time = [
            e.attrib["ft"] for e in root.xpath(
                f"//station[@id=\'{station}\']/progs/prog")][when]

        title = title.replace("▽", "  ")

        self.logger.debug(f"station_name: {self.station_name}")
        self.logger.debug(f"title       : {title}")
        self.logger.debug(f"artwork_url : {artwork_url}")
        self.logger.debug(f"start_time  : {self.start_time}")
        self.logger.debug(f"end_time    : {self.end_time}")

        ext = ""
        if artwork_url != "":
            ext = os.path.splitext(artwork_url)[1].lower()

        self.artwork_type_check(ext, artwork_url, title)

        return True

    def follow_pg_info(self, station):
        self.station_name = ""
        self.start_time = ""
        self.end_time = ""

        title = ""
        artwork_url = ""
        if station != "":
            self.logger.debug(f"station option artwork: {station}")
            if artwork_ip == "" or artwork_ip is None:
                art_ip = "127.0.0.1"
            else:
                art_ip = artwork_ip

            for file in glob.iglob(f"/config/artwork_option/{station}.*"):
                self.logger.debug(f"station option artwork file: {file}")
                if os.path.splitext(file)[1].lower() in [".jpg", ".png"]:
                    file_url = f"artwork_opt/{os.path.basename(file)}"
                    title = f"station_id: {station}"
                    artwork_url = f"http://{art_ip}:{PORT}/{file_url}"

        self.update_metadata_file(title, artwork_url)

        return

    # forked-daapd displayed when the extension is ".jpg" and "png"
    def artwork_type_check(self, ext, artwork_url, title):
        dst_path = "/tmp/artwork"
        if not os.path.exists(dst_path):
            os.mkdir(dst_path)

        if ext in [".jpeg", ".gif"]:
            file_name = os.path.basename(
                os.path.splitext(artwork_url)[0]
            ) + ".jpg"
            artwork_path = os.path.join(dst_path, file_name)

            if not os.path.exists(artwork_path):
                res = self.make_request(artwork_url)
                img = Image.open(io.BytesIO(res.content)).convert('RGB')
                img.save(artwork_path, quality=95)

            if artwork_ip == "" or artwork_ip is None:
                art_ip = "127.0.0.1"
            else:
                art_ip = artwork_ip

            artwork_url = f"http://{art_ip}:{PORT}/artwork/{file_name}"
            self.logger.debug(f"artwork file name: {file_name}")
            self.logger.debug(f"artwork path: {artwork_path}")

        self.update_metadata_file(title, artwork_url)

        return True

    # update stream metadata file(title & artwork_url) for ezstream
    def update_metadata_file(self, title, artwork_url):
        if not os.path.exists("/ezstream"):
            os.mkdir("/ezstream")
        title_path = "/ezstream/title.txt"

        StreamUrl = ""
        if artwork_url != "":
            StreamUrl = f"\';StreamUrl={artwork_url}"
        if title != "":
            title = f"{title}{StreamUrl}"

        with open(title_path, "w") as f:
            f.write(f"{title}\n")

        return

    # ezstream config file update
    def update_ezstream_config(self, format, station_name):
        path_xml = f"/ezstream/ezstream-radio_{format}.xml"
        if not os.path.exists(path_xml):
            self.logger.error("ezstream xml file not found")
            return False

        ez_tree = LET.parse(path_xml)
        ice_name = [
            e for e in ez_tree.xpath(
                "/ezstream/streams/stream/stream_name")][0]

        ice_name.text = station_name

        ez_tree.write(path_xml, xml_declaration = True, encoding="utf-8")

        return True

    def play_cmd(self, input, format, volume=5, duration=None):
        self.logger.debug("make play_cmd")

        if format == "MP3":
            options = '-c:a libmp3lame -content_type "audio/mpeg" -f mp3 '
            options += f'-af "volume={volume}dB" '

        if format == "OGG":  # Test only
            options = '-c:a libvorbis -content_type "audio/ogg" -f ogg '

        if format == "FLAC":  # Test only, NG
            options = '-c:a flac -content_type "audio/flac" -f flac '

        if format == "AAC":
            options = '-c:a copy -content_type "audio/aac" -f adts '

        # options += f"-rtbufsize 512kB -bufsize 512kB "

        # need -re option. IMHO,ffmpeg send stop at buffer overflow?
        player_cmd = f'ffmpeg -y -loglevel panic -re -i "{input}" -vn {options} -'

        return player_cmd

