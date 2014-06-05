from matahn import app

from flask import jsonify, render_template, request, abort, redirect, url_for, send_from_directory, send_file
import os
import time
import re

from matahn.models import Tile, Task
from matahn.database import db_session
from matahn.util import get_ewkt_from_bounds

from matahn.tasks import new_task

from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound


@app.route("/")
def matahn():
    return render_template("index.html")


@app.route("/_getDownloadArea")
def getDownloadArea():
    geojson = db_session.query(func.ST_AsGeoJSON(func.ST_Union(Tile.geom))).one()[0]
    return jsonify(result=geojson)

@app.route("/_getTaskArea")
def getTaskArea():
    #should prob validate this
    task_id = request.args.get('task_id', type=str)
    geojson = db_session.query(func.ST_AsGeoJSON(Task.geom)).filter(Task.id==task_id).one()[0]
    return jsonify(result=geojson)


@app.route("/_getPointCountEstimate")
def getPointCountEstimate():
    """Gives an estimate of the number of points in the query rectangle"""
    left = request.args.get('left', type=float)
    bottom = request.args.get('bottom', type=float)
    right = request.args.get('right', type=float)
    top = request.args.get('top', type=float)

    ewkt = get_ewkt_from_bounds(left, bottom, right, top)

    tiles = db_session.query(   Tile.pointcount \
                                * \
                                func.ST_Area( Tile.geom.ST_Intersection(ewkt) ) / Tile.geom.ST_Area() \
                            ).filter(Tile.geom.intersects(ewkt))
    
    total_estimate = sum( [ v[0] for v in tiles ] )

    if total_estimate > 1e6:
        return jsonify(result="You selected about {:.0f} million points!".format(total_estimate/1e6))
    elif total_estimate >1e3:
        return jsonify(result="You selected about {:.0f} thousand points!".format(total_estimate/1e3))
    else:
        return jsonify(result="You selected about {:.0f} points!".format(total_estimate))


@app.route("/_submit")
def submitnewtask():
    left  = request.args.get('left', type=float)
    bottom  = request.args.get('bottom', type=float)
    right  = request.args.get('right', type=float)
    top  = request.args.get('top', type=float)
    email = request.args.get('email', type=str)
    classification = request.args.get('classification', type=str)

    # TODO: area selected: define a max value here?

    # email validation
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify(wronginput = "email is not valid")
    # classification validation
    if not re.match(r"^(?=\w{1,2}$)([ug]).*", classification):
        return jsonify(wronginput = "wrong AHN2 classification")
    # selection bounds validation
    if 0 == db_session.query(Tile).filter( Tile.geom.intersects( get_ewkt_from_bounds(left, bottom, right, top) ) ).count():
        return jsonify(wronginput = "selection is empty")

    # new celery task
    result = new_task.apply_async((left, bottom, right, top, classification))
    # store task parameters in db
    task = Task(id=result.id, ahn2_class=classification, emailto=email, geom=get_ewkt_from_bounds(left, bottom, right, top) )
    db_session.add(task)
    db_session.commit()

    taskurl = url_for('tasks_page', task_id=result.id)
    return jsonify(result = taskurl)


@app.route('/tasks/download/<filename>', methods=['GET'])
def tasks_download(filename):
    if app.debug:
        return send_file(app.config['RESULTS_FOLDER'] + filename)


@app.route('/tasks/<task_id>')
def tasks_page(task_id):
    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', task_id):
        return render_template("tasknotfound.html"), 404
    try:
        task = db_session.query(Task).filter(Task.id==task_id).one()
    except NoResultFound:
        return render_template("tasknotfound.html"), 404

    status = task.get_status()
    if status == 'SUCCESS':
        filename = app.config['RESULTS_FOLDER'] + task_id + '.laz'
        if (os.path.exists(filename)):
            return render_template("index.html", task_id = task.id, status='okay', download_url=task.get_relative_url())
        else:
            return render_template("index.html", task_id = task.id, status='deleted')
    else:
        return render_template("index.html", task_id = task.id, status='pending', refresh=True)








