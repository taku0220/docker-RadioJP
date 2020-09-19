#!/usr/bin/env python3

import os
import sys

from radiko import RadikoHLS
from radiru import RadiruHLS

# general config
from setting.general_config import *

radiko = RadikoHLS()
radiru = RadiruHLS()


class Playlist:

    def __init__(self):
        pass

    def Radiko_pl(self):
        company = "radiko"

        if radiko.access_auth() is False:
            sys.stderr.write("Radiko exec access_auth failed.\n")
            return False
        if radiko.get_area_id() is False:
            sys.stderr.write("Radiko exec get_area_id failed.\n")
            return False
        area = radiko.area_id

        stations = radiko.get_stations()
        if stations is False:
            sys.stderr.write("Radiko exec get_stations failed.\n")
            return False

        Radiko_dir = f"{self.pl_dir}/{company}"
        if not os.path.exists(Radiko_dir):
            os.mkdir(Radiko_dir)

        all_path = f"{Radiko_dir}/Radiko.m3u"

        with open(all_path, "w") as fa:
            fa.write("#EXTM3U\n")

            for station in stations:
                out_path = f"{Radiko_dir}/{station}_{area}.m3u"
                m3u1 = f"#EXTINF:-1,{area} - {station}\n"
                m3u2 = f"{playlist_url}:{PORT}/{company}/{station}/{area}\n"

                fa.write(m3u1)
                fa.write(m3u2)
                with open(out_path, "w") as f:
                    f.write("#EXTM3U\n")
                    f.write(m3u1)
                    f.write(m3u2)

        return

    def Radiru_pl(self):
        company = "radiru"

        Radiru_dir = f"{self.pl_dir}/{company}"
        if not os.path.exists(Radiru_dir):
            os.mkdir(Radiru_dir)

        all_path = f"{Radiru_dir}/Radiru.m3u"

        with open(all_path, "w") as fa:
            fa.write("#EXTM3U\n")

            for area in radiru.areas:
                for station in radiru.stations:
                    out_path = f"{Radiru_dir}/{station}_{area}.m3u"
                    m3u1 = f"#EXTINF:-1,{area} - {station}\n"
                    m3u2 = f"{playlist_url}:{PORT}/{company}/{station}/{area}\n"

                    fa.write(m3u1)
                    fa.write(m3u2)
                    with open(out_path, "w") as f:
                        f.write("#EXTM3U\n")
                        f.write(m3u1)
                        f.write(m3u2)

        return

    def main(self):
        # Playlist format: Base_URL/company/station_id/area_id
        sys.stdout.write("Radiko and Radiru make Playlist start.\n")

        self.pl_dir = "/config/playlist"
        if not os.path.exists(self.pl_dir):
            os.mkdir(self.pl_dir)

        # Radiko
        if self.Radiko_pl() is False:
            sys.stderr.write("Radiko Playlist make failed.\n")

        # Radiru
        if self.Radiru_pl() is False:
            sys.stderr.write("Radiru Playlist make failed.\n")

        return

if __name__ == '__main__':
    plist = Playlist()
    plist.main()
    sys.stdout.write("make Playlist comp.\n")
    sys.exit(0)
