#!/usr/bin/env python3

import glob
import os
import requests
import shlex
import signal
import time
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from flask import  abort, Flask, request, Response, \
                   send_from_directory, stream_with_context
from logging import config, getLogger
from werkzeug.serving import WSGIRequestHandler

from radiko import RadikoHLS
from radiru import RadiruHLS
from function import Function

# general config
from setting.general_config import *

# logging config
from setting.logging_config import log_config
config.dictConfig(log_config)

radiko = RadikoHLS(logger=getLogger("docker-radio"))
radiru = RadiruHLS(logger=getLogger("docker-radio"))
Func = Function(logger=getLogger("docker-radio"))


class Radio(Flask):

    ice_alive = False
    ffmpeg_pid = None
    ezstream_pid = None
    old_req = ""
    old_req_sc = 500

    def __init__(self, *args, **kwargs):
        Flask.__init__(self, *args, **kwargs)

    # job: icecast server check
    def ice_alive_check(self):
        self.ice_alive = False

        res = Func.make_request(ice_url, headers=dict(my_headers), s_code=200)
        if res is False:
            app.logger.error("icecast server not alive!!")
            return

        self.ice_alive = True
        app.logger.debug("icecast server alive, OK")

        return

    # job: tmp folder cleaning
    def tmp_cleaning(self):
        file_list = glob.glob("/tmp/artwork/*.jpg")
        for file in file_list:
            atime = datetime.fromtimestamp(os.path.getatime(file))
            delta = datetime.now() - atime
            app.logger.debug(f"file: {file}")
            app.logger.debug(f"atime: {atime}")
            app.logger.debug(f"delta: {delta.total_seconds()} sec")
            if delta.total_seconds() >= (tmp_limit * 60 * 60):
                app.logger.debug("this file is time over")
                os.remove(file)

        return

    # scheduler: add update program info job
    def add_update_program_info_job(self, end_time):
        check_job = app.scheduler.get_job("job_upi")
        if check_job is not None:
            return

        run_time = end_time - timedelta(seconds=3)
        app.scheduler.add_job(
            self.update_program_info, "date", run_date=run_time,
            id="job_upi", args=[end_time]
        )
        check_job = app.scheduler.get_job("job_upi")
        app.logger.debug(f"check add job: {check_job}")

        return

    # scheduler: delete update program info job
    def del_update_program_info_job(self):
        check_job = app.scheduler.get_job("job_upi")
        app.logger.debug(f"check remove job: {check_job}")

        if check_job is not None:
            app.scheduler.remove_job("job_upi")
            all_jobs = app.scheduler.get_jobs()
            app.logger.debug(f"remained jobs: {all_jobs}")

        return

    # job: update program info job
    def update_program_info(self, end_time):
        if self.old_req == "" or self.ezstream_pid is None:
            app.logger.error("next program info: update failed")
            return

        dummy, company, station_id, area_id = self.old_req.rsplit("/")
        if company == "radiru":
            area_id = radiru.areas_radiko[radiru.areas.index(area_id)]
            station_index = radiru.stations.index(station_id)
            station_id = radiru.stations_radiko[area_id][station_index]
            self.logger.debug(f"radiko_area   : {area_id}")
            self.logger.debug(f"radiko_station: {station_id}")
        Func.get_program_info(area_id, station_id, 1)

        update_delay = eval(f"{company}_delay")
        self.logger.debug(f"update_delay   : {update_delay}[sec]")
        take_time = end_time + timedelta(seconds=update_delay)
        take_standby = take_time - timedelta(milliseconds=200)
        time.sleep((take_standby - datetime.now()).total_seconds())

        count = 0
        if self.check_pid(self.ezstream_pid) is True:
            while True:
                count += 1
                if datetime.now() >= take_time:
                    os.kill(self.ezstream_pid, signal.SIGUSR2)  # SIGUSER2 signal
                    app.logger.debug(f"next program info: push ezstream[{count}]")
                    break
                time.sleep(0.1)

        new_end_time = datetime.strptime(Func.end_time, "%Y%m%d%H%M%S")
        # if new_end_time is passed.
        if datetime.now() >= new_end_time:
            app.logger.debug("new_end_time is passed.")
            while True:
                time.sleep(120)
                app.logger.debug("retry get next program info")
                Func.get_program_info(area_id, station_id, 1)
                new_end_time = datetime.strptime(Func.end_time, "%Y%m%d%H%M%S")
                if new_end_time >= datetime.now():
                    break

        self.add_update_program_info_job(new_end_time)
        app.logger.info("next program info: update success")

        return

    # output stream generater
    def generate(self, res):
        app.logger.info("start stream output")
        used_ffmpeg = self.ffmpeg_pid
        try:
            for chunk in res.iter_content(chunk_size, decode_unicode=False):
                yield chunk
        except requests.exceptions.RequestException as err:
            app.logger.error(f"icecast server error: {err}")  # icecast down
        finally:
            app.logger.info("icecast server close")  # when client close
            time.sleep(1)
            if self.check_pid(used_ffmpeg) is True:
                self.add_generater_down_delay_job(used_ffmpeg, 10)

        return

    # scheduler: add generater down delay job
    def add_generater_down_delay_job(self, pid, interval):
        id = f"job_ffmpeg{pid}"
        run_time = datetime.now() + timedelta(seconds=interval)
        if app.scheduler.get_job(id) is None:
            app.scheduler.add_job(
                self.generater_down_delay, "date", run_date=run_time,
                id=id, args=[pid]
            )
            check_job = app.scheduler.get_job(id)
            app.logger.debug(f"check add job: {check_job}")

        return

    # job: generater down delay job
    def generater_down_delay(self, pid):
        if self.check_pid(pid) is True:
            app.logger.info(
                f"waiting for generater_down_delay: Shutdown start[{pid}]"
            )
            self.ffmpeg_kill(pid)
        else:
            app.logger.debug(
                f"waiting for generater_down_delay: already stopped[{pid}]"
            )

    # ffmpeg process kill
    def ffmpeg_kill(self,pid=None):
        if self.old_req != "":
            proc_company = self.old_req.split("/")[1]

        if pid is None:
             if self.ffmpeg_pid is not None:
                 pid = self.ffmpeg_pid

        if pid is not None:
            if self.check_pid(pid) is True:
                app.logger.debug(f"kill pid-1: {pid}")
                os.kill(pid, signal.SIGKILL)
                app.logger.debug(f"kill pid-2: {pid}")
                if proc_company != "":
                    eval(proc_company).p1.wait()

        if self.ezstream_pid is not None:
            if self.check_pid(self.ezstream_pid) is True:
                os.kill(self.ezstream_pid, signal.SIGTERM)
                # for debug
                if EZ_DEBUG is True:
                    proc = eval(proc_company).p2
                    while True:
                        ez_err = proc.stderr.read(64)
                        app.logger.debug(f"ez_err: {ez_err}")
                        if proc.poll() is not None:
                            break

                if proc_company != "":
                    eval(proc_company).p2.wait()

        app.logger.debug("ff ez down")
        self.del_update_program_info_job()
        self.ffmpeg_pid = None
        self.ezstream_pid = None
        self.old_req = ""
        self.old_req_sc = 500

    # process check
    def check_pid(self, pid):
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True


app = Radio(__name__)

@app.route("/<string:company>/<string:station_id>/<string:area_id>", methods=["GET"])
def play(company, station_id, area_id):
    # same request?
    same_request = False
    if request.path == app.old_req and app.old_req_sc == 200:
        same_request = True

    # Radiko or Radiru?
    app.logger.info(f"company: [{company}]")
    if not company in ["radiko", "radiru"]:
        abort(404)

    # if ffmpeg already playback
    app.logger.debug(f"old ffmpeg_pid: {app.ffmpeg_pid}")
    if app.ffmpeg_pid is not None:
        app.logger.debug("ffmpeg already playback: will terminated")
        app.ffmpeg_kill()

    # icecast is alive
    if app.ice_alive is False:
        app.logger.error("icecast server connection failed.")
        abort(500)

    # play start
    app.logger.info(f"player exec try:[{station_id}]")
    volume = eval(f"{company}_volume")
    play = eval(company).play_radio(station_id, area_id, format.upper(), volume)
    if play is False:
        app.logger.error("player exec failed.")
        abort(500)

    app.ffmpeg_pid = eval(company).p1.pid
    app.ezstream_pid = eval(company).p2.pid
    app.old_req = request.path
    app.old_req_sc = 0

    app.logger.debug(f"ffmpeg_pid      : {app.ffmpeg_pid}")
    app.logger.debug(f"ezstream_pid    : {app.ezstream_pid}")
    app.logger.debug(f"now request     : {app.old_req}")

    # if forked-daapd pause command
    if same_request is True:
        app.add_generater_down_delay_job(app.ffmpeg_pid, 5)

    # add job "update program info"
    if eval(company).start_time != "":
        start_time = datetime.strptime(eval(company).start_time, "%Y%m%d%H%M%S")
        app.logger.debug(f"start_time      : {start_time}")
    if eval(company).end_time != "":
        end_time = datetime.strptime(eval(company).end_time, "%Y%m%d%H%M%S")
        app.logger.debug(f"end_time        : {end_time}")

    # test_time = datetime.now() + timedelta(seconds=30)  # job test
    # app.add_update_program_info_job(test_time)  # job test
    if eval(company).end_time != "":
        app.add_update_program_info_job(end_time)

    time.sleep(0.4)

    # proxy icecast server
    """
    A simple proxy server, based on original by gear11:
    https://gist.github.com/gear11/8006132
    https://gist.github.com/stewartadam/f59f47614da1a9ab62d9881ae4fbe656
    thanks Andy Jenkins @gear11, Stewart Adam @stewartadam
    """
    url = f"{ice_url}{ice_mount}"
    for i in range(10):
        res = Func.make_request(url, headers=dict(request.headers),stream=True)
        if res is False:
            continue

        app.logger.debug(f"Got {res.status_code} response from {url}")
        if res.status_code == 200:
            break
        elif i == 9:
            app.logger.error(f"icecast server not start playback.[{i}]")
            app.ffmpeg_kill()
            abort(500)
        time.sleep(0.2)

    headers = dict(res.raw.headers)
    out = Response(stream_with_context(app.generate(res)), headers=headers)
    out.status_code = res.status_code
    app.old_req_sc = res.status_code

    app.logger.debug(f"send headers: {headers}")

    return out

@app.route("/artwork/<string:file_name>", methods=["GET"])
def artwork(file_name):
    src_dir = "/tmp/artwork"
    file_path = f"{src_dir}/{file_name}"
    mtime = os.path.getmtime(file_path)
    atime = time.time()
    os.utime(file_path, (atime, mtime))

    return send_from_directory(src_dir, file_name, mimetype = "image/jpeg")

@app.route("/artwork_opt/<string:file_name>", methods=["GET"])
def artwork_opt(file_name):
    src_dir = "/config/artwork_option"
    file_path = f"{src_dir}/{file_name}"
    mtime = os.path.getmtime(file_path)
    atime = time.time()
    os.utime(file_path, (atime, mtime))

    return send_from_directory(src_dir, file_name, mimetype = "image/jpeg")

@app.before_request
def before_request():
    app.logger.info("##### Request start ##############################")
    app.logger.debug(f"new request path : {request.path}")
    app.logger.debug(f"old request path : {app.old_req}")


def main():
    app.debug = DEBUG
    app.logger = getLogger("docker-radio")
    WSGIRequestHandler.protocol_version = "HTTP/1.1"

    app.ice_alive_check()

    job_defaults = {"coalesce": False, "max_instances": 8}
    app.scheduler = BackgroundScheduler(daemon=True, job_defaults=job_defaults)
    app.scheduler.add_job(
        app.ice_alive_check,"interval", seconds=ice_ping, id="job_ice_check"
    )
    cleaning_time = 24 * 60 * 60
    app.scheduler.add_job(
        app.tmp_cleaning,"interval", seconds=cleaning_time, id="job_tmp_clean"
    )
    app.scheduler.start()

    try:
        app.run(host=HOST, port=PORT, use_reloader=False)

        """
        app.run(
            debug=True, use_reloader=False, host=HOST, port=PORT,
            use_debugger=True, passthrough_errors=False
        )
        """
    finally:
        print ("docker-radio quit\n")
        os.system('stty sane')

if __name__ == "__main__":
    main()

