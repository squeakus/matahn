# This file is part of MATAHN.

# MATAHN is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# MATAHN is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with MATAHN.  If not, see <http://www.gnu.org/licenses/>.

# Copyright 2014 Ravi Peters, Hugo Ledoux

from flask import render_template, url_for
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime
from geoalchemy2 import Geometry

import matahn
from matahn import app
from matahn.database import Base

class Tile(Base):
    __tablename__ = 'tiles'
    id = Column(Integer, primary_key=True)
    path = Column(String, unique=True)
    ahn2_bladnr = Column(String(5))
    ahn2_class = Column(String(1))
    active = Column(Boolean)
    pointcount = Column(Integer)
    geom = Column(Geometry('POLYGON', srid=28992))

    def __repr__(self):
    	return "tile {}_{}".format(self.ahn2_bladnr, self.ahn2_class)

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(String, primary_key=True)
    ahn2_class = Column(String(2))
    emailto = Column(String)
    ip_address = Column(String)
    time_stamp = Column(DateTime)
    geom = Column(Geometry('POLYGON', srid=28992))
    log_execution_time = Column(Float)
    log_actual_point_count = Column(Integer)

    def __repr__(self):
        return "task {}".format(self.id)

    def get_status(self):
        async_result = matahn.tasks.new_task.AsyncResult(self.id)
        return async_result.status

    def get_filename(self):
        return self.id + '.laz'

    def get_absolute_path(self):
        return app.config['RESULTS_FOLDER'] + self.get_filename()

    def get_relative_url(self):
        return app.config['STATIC_DOWNLOAD_URL'] + self.get_filename()

    # def relaunch(self):
    #     # new celery task
    #     result = matahn.tasks.new_task.apply_async((left, bottom, right, top, classification))
    #     # store task parameters in db
    #     task = Task(id=result.id, ahn2_class=self.ahn2_class, emailto=self.emailto, geom=get_ewkt_from_bounds(left, bottom, right, top) )
    #     db_session.add(task)
    #     db_session.commit()
    #     return task

    def send_email(self):
        import smtplib
        from email.mime.text import MIMEText

        receiver = self.emailto
        body = render_template('mail_download_notification.html', task_url='http://'+app.config['SERVER_NAME']+'/matahn/tasks/'+self.id)
        msg = MIMEText(body)
        msg['Subject'] = 'Your AHN2 file is ready'
        msg['From'] = app.config['MAIL_FROM']
        msg['To'] = receiver
        
        s = smtplib.SMTP_SSL( app.config['MAIL_SERVER'] )
        s.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        s.sendmail(app.config['MAIL_FROM'], [receiver], msg.as_string())
        s.quit()