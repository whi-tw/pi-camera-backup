import http
import subprocess

from flask import Flask, request, redirect, render_template, jsonify
from urllib.parse import urlparse


from concurrent.futures import ThreadPoolExecutor

from pibackup import configuration, directory, backup, display


executor = ThreadPoolExecutor(2)

config = configuration.ConfigManager()
directory_manager = directory.DirManager(config)
backup_manager = backup.BackupManager(config, directory_manager)
display_manager = display.DisplayManager(config, directory_manager)



app = Flask(__name__)

@app.route('/')
def home():
    vars = {
        "filebrowser_base": "{}://{}:{}".format(
            request.scheme, urlparse(request.base_url).hostname,
            config.filebrowser_port),
    }
    return render_template('home.html', **vars)

@app.route('/backup')
def backup():
    return render_template('backup.html')


@app.route('/api/backup', methods=['GET', 'POST'])
def run_backup():
    if backup_manager.current_job is not None:
        if request.method == 'POST':
            return "Backup already running. Start time: {}".format(
                backup_manager.current_job.start_time
            ), http.HTTPStatus.CONFLICT
        return backup_manager.current_job.run_time(), http.HTTPStatus.OK
    if request.method == 'GET':
        return "No backup currently running", http.HTTPStatus.NOT_FOUND
    executor.submit(backup_manager.do_backup)
    return "Backup started", http.HTTPStatus.CREATED

@app.route('/filebrowser')
def redir_to_filebrowser():
    return redirect("{}://{}:{}".format(
        request.scheme, urlparse(request.base_url).hostname,
        config.filebrowser_port
    ), http.HTTPStatus.MOVED_PERMANENTLY)

@app.route('/api/shutdown', methods=["POST"])
def shutdown_pi():
    shutdown = subprocess.run(
        ["systemctl", "poweroff"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    resp = app.make_response(
        str({
            'stderr': shutdown.stderr,
            'stdout': shutdown.stdout,
            'return': shutdown.returncode
        })
    )
    resp.status_code = http.HTTPStatus.CREATED
    resp.mimetype = 'application/json'
    return resp

@app.route('/api/chartdata', methods=["GET"])
def chart_data():
    data = display_manager.getChartData()
    return jsonify(data), http.HTTPStatus.OK

@app.route('/api/backups', methods=["GET"])
def backup_list():
    data = display_manager.getBackupData()
    return jsonify(data), http.HTTPStatus.OK


@app.route('/api/config/<conf_name>', methods=["GET"])
def get_config(conf_name):
    if conf_name == 'config':
        data = dict(config)
    elif conf_name == 'directories':
        data = dict(directory_manager)
    try:
        print(data)
        return jsonify(data), http.HTTPStatus.OK
    except UnboundLocalError:
        return jsonify({}), http.HTTPStatus.NOT_FOUND
