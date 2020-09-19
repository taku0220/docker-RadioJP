#!/usr/bin/env python3

import os
import sys
from lxml import etree as LET

# general config
from setting.general_config import *


class radio_config:

    icecast_file = "/etc/icecast.xml"
    ezstream_file = "/ezstream/ezstream-radio_{}.xml"

    def __init__(self):
        sys.stdout.write("config update\n")
        if self.conf_load() is False:
            sys.exit(1)
        
        self.update_flag = 0

    def conf_load(self):
        confs = [ice_url, ice_mount, ice_pass, ice_loglevel]
        keys = ["HOST", "MOUNT", "PASS" ,"LOGLEVEL"]
        for conf, key in zip(confs, keys):
            if conf:
                setattr(self, key, conf)
                # sys.stdout.write(f"{key}: {conf}\n")
            else:
                sys.stderr.write(f"{conf}の設定値がありません\n")
                return False

        dummy, ret_host, self.PORT = self.HOST.rsplit(":", 2)
        self.HOST = ret_host.rsplit("/", 1)[1]

        return True

    # xml: file open and read
    def xml_init(self, file_path):
        if os.path.exists(file_path):
            self.xml_tree = LET.parse(file_path)
        else:
            sys.stderr.write(f"{file_path}が見つかりません\n")
            return False

        return True

    # xml: get now_conf and set new_conf
    def xml_conf_set(self, path, new_conf):
        tags = self.xml_tree.xpath(path)
        for tag in tags:
            # sys.stdout.write(f"tag: {tag.text}\n")
            if len(tag.text) and tag.text != str(new_conf):
                # sys.stdout.write(f"update tag: {tag.text}\n")
                tag.text = str(new_conf)
                self.update_flag += 1
                return

        return


    def set_icecast(self):
        sys.stdout.write("start icecast config update\n")
        ret = self.xml_init(self.icecast_file)
        if ret is False:
            return False

        self.xml_conf_set("//listen-socket/bind-address", self.HOST)
        self.xml_conf_set("//listen-socket/port", self.PORT)
        self.xml_conf_set("//mount/mount-name", self.MOUNT)
        self.xml_conf_set("//authentication/source-password", self.PASS)
        self.xml_conf_set("//authentication/admin-password", self.PASS)
        self.xml_conf_set("//logging/loglevel", self.LOGLEVEL)

        if self.update_flag != 0:
            self.xml_tree.write(
                self.icecast_file, xml_declaration = False, encoding="utf-8"
            )
            sys.stdout.write("  icecast config update comp\n")
        else:
            sys.stdout.write("  icecast config no changed\n")

        self.xml_tree = ""

        return

    def set_ezstream(self):
        sys.stdout.write("start ezstream config update\n")
        if self.update_flag == 0:
            sys.stdout.write("  ezstrem[all format] config no changed\n")
            return

        ez_format = ["AAC", "MP3", "OGG", "FLAC"]
        for format in ez_format:
            file_path = self.ezstream_file.format(format)
            ret = self.xml_init(file_path)
            if ret is False:
                continue

            self.update_flag = 0
            self.xml_conf_set("//server/hostname", self.HOST)
            self.xml_conf_set("//server/port", self.PORT)
            self.xml_conf_set("//stream/mountpoint", self.MOUNT)
            self.xml_conf_set("//server/password", self.PASS)

            if self.update_flag != 0:
                self.xml_tree.write(
                    file_path, xml_declaration = True, encoding="utf-8"
                )
                sys.stdout.write(f"  ezstrem[{format}] config update comp\n")
            else:
                sys.stdout.write(f"  ezstrem[{format}] config no changed\n")

            self.xml_tree = ""

        self.xml_tree = ""

        return


    def main(self):
        ret = self.set_icecast()
        if ret is False:
            sys.exit(1)

        self.set_ezstream()

        return

if __name__ == "__main__":
    conf = radio_config()
    conf.main()
    sys.exit(0)
