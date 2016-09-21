#!/usr/bin/env python

from sense_hat import SenseHat
from datetime import datetime
import os
from os.path import getmtime
import sys
import numpy as np
import time
import dateutil
import dateutil.tz

import emdash
import emdash.config
import emdash.handlers

import jsonrpc.proxy

EXECUTABLE = "/usr/local/bin/emdash_environment.py"
WATCHED_FILES = [__file__,EXECUTABLE]
WATCHED_FILES_MTIMES = [(f, getmtime(f)) for f in WATCHED_FILES]

def gettime():
    return datetime.now(dateutil.tz.gettz())

def main():
	ns = emdash.config.setconfig()
	config = emdash.config.Config()
	
	this = gettime()
	print("Init: {}".format(this))
	
	print("Host: {}".format(config.get("host")))
	print("User: {}".format(config.get("username")))
	print("Protocol: {}".format(config.get("session_protocol")))
	
	sys.stdout.flush()
	
	logged_in = False
	while logged_in is False:
		try:
			print("LOGGING IN...")
			db = config.db()
			ctxid = db.login(config.get("username"),config.get("password"))
			emdash.config.set("ctxid",ctxid)
			logged_in = True
			print("SUCCESS.")
			context = db.checkcontext()
			print("Context: {}".format(context[1]))
		except Exception,e:
			print("FAILED ({}). Will try again in 5 seconds.".format(e))
			logged_in = False
			time.sleep(5)
		sys.stdout.flush()
	
	room = db.record.get(config.get("room_id"))
	print("CTXID: {}".format(ctxid))
	print("Record #{}".format(config.get("room_id")))
	print("Name: {}".format(room["room_name"]))
	
	sys.stdout.flush()

	sense = EMSenseHat()
	sense.clear()
		
	last = {}
	last["second"] = int(this.second)
	last["minute"] = int(this.minute)
	last["hour"] = int(this.hour)
	last["day"] = int(this.day)

	high_temp = 25.  # alert if temperature > this
	high_humid = 45. # alert if humidity > this

	samples = []

	log = EMSensorLog(config)
	
	try:
		while True:
			this = gettime()
			
			# Every second
			if this.second != last["second"]:
				data = sense.get_environment()
				samples.append(data)
				sense.update_display()
				last["second"] = this.second
			
			# Every minute
			if this.minute != last["minute"]:
				avg = np.mean(samples,axis=0)
				log.write(avg)
				samples = []
				sense.alert(avg[0],avg[1])
				last["minute"] = this.minute
			
			# Every day
			if this.day != last["day"]:
				sys.stdout.flush()
				rec = log.upload(db)
				sys.stdout.flush()
				sense.reset_maxima()
				last["day"] = this.day
			
			# Every hour
			if this.hour != last["hour"]:
				last["hour"] = this.hour

			for f, mtime in WATCHED_FILES_MTIMES:
				if getmtime(f) != mtime:
					os.execv(EXECUTABLE,sys.argv)
	
	except KeyboardInterrupt:
		sense.clear()

class EMSensorLog:

	def __init__(self,conf):
		self.start_date = gettime()
		self.ah = AttachmentHandler()
		self.ah.name = "/home/pi/logs/{}.csv".format(self.start_date.date())
		self.ah.header = ["timestamp","temperature","humidity","pressure"]
		if not os.path.isfile(self.ah.name):
			with open(self.ah.name,"w") as f:
				f.write("#{}\n".format(",".join(self.ah.header)))

	def write(self,data,rnd=1):
		n = gettime()
		with open(self.ah.name,"a") as f:
			dat = ",".join([str(round(val,rnd)) for val in data])
			out = "{},{}\n".format(n,dat)
			f.write(out)
	
	def read(self):
		data = []
		with open(self.ah.name,"r") as f:
			for i,l in enumerate(f):
				if i > 0: # skip header
					line = l.strip().split(",")
					data.append(line[1:])
		return np.asarray(data).astype(float)
	
	def upload(self,db):
		self.end_date = gettime()
		data = self.read()
		
		t_high,h_high,p_high = np.max(data,axis=0)
		t_low,h_low,p_low = np.min(data,axis=0)
		t_avg,h_avg,p_avg = np.mean(data,axis=0)
		
		config = emdash.config.Config()
		room = db.record.get(config.get("room_id"))
		
		rec = {}
		
		rec[u'parents'] = room['name']
		rec[u'groups'] = room['groups']
		rec[u'permissions'] = room['permissions']
		rec[u'rectype'] = config.get("session_protocol")
		
		rec[u'room_name'] = room["room_name"]
		
		rec[u'date_start'] = self.start_date.isoformat()
		rec[u'date_end'] = self.end_date.isoformat()
		
		rec[u'temperature_ambient_low'] = round(t_low,1)
		rec[u'temperature_ambient_high'] = round(t_high,1)
		rec[u'temperature_ambient_avg'] = round(t_avg,1)
		
		rec[u'humidity_ambient_low'] = round(h_low,1)
		rec[u'humidity_ambient_high'] = round(h_high,1)
		rec[u'humidity_ambient_avg'] = round(h_avg,1)
		
		rec[u'pressure_ambient_low'] = round(p_low,1)
		rec[u'pressure_ambient_high'] = round(p_high,1)
		rec[u'pressure_ambient_avg'] = round(p_avg,1)
		
		rec[u'comments'] = ""
		
		rec.update()
		
		record = db.record.put(rec)
		
		self.ah.target = record["name"]
		
		record = self.ah.upload()
		
		return record
	
	def new(self):
		try: # remove local file after upload is complete
			os.unlink(self.ah.name)
		except:
			n = gettime()
			print("{}\tWARNING: Failed to remove {}".format(n,self.ah.name))
			sys.stdout.flush()
		
		self.ah.name = "/home/pi/logs/{}.csv".format(self.end_date.date())
		self.start_date = gettime()

class EMSenseHat(SenseHat):
	OFF_PIXEL=[0,0,0]
	MAX_PIXEL = [100,100,100]
	GOOD_PIXEL = [0,100,100]
	BAD_PIXEL = [100,0,0]
	WARN_PIXEL = [100,100,0]
	ALERT_PIXEL = [100,100,100]
	
	max_recorded_temp = 0.
	max_recorded_humidity = 0.
	
	good_temp = 23.
	bad_temp = 28.
	
	good_humidity = 35.
	bad_humidity = 45.
	
	max_temp = 40.0
	min_temp = 10.0
	
	def get_environment(self,rnd=1):
		T = round(self.temperature,rnd)
		H = round(self.humidity,rnd)
		P = round(self.pressure,rnd)
		return [T,H,P]
	
	def reset_maxima(self):
		self.max_recorded_humidity = 0.
		self.max_recorded_temp = 0.
	
	def auto_rotate(self):
		ar = self.get_accelerometer_raw()
		x = round(ar["x"])
		y = round(ar["y"])
		if x == -1: rot=0
		elif y == -1: rot=90
		elif x == 1: rot=180
		else: rot = 270
		self.set_rotation(rot)

	def update_display(self):
		self.auto_rotate()
		
		# Temperature Bar
		t_pixels = []
		
		if self.temp >= self.max_temp:
			t_on_count = 16
		elif self.temp < 0:
			t_on_count = 0
		else:
			norm_t = (self.temp-self.min_temp)/(self.max_temp-self.min_temp)
			t_on_count = int(round(16.*norm_t))
		
		t_off_count = 16-t_on_count
		
		if self.temp <= self.good_temp:
			t_pixels.extend([self.GOOD_PIXEL] * t_on_count)
		elif self.temp <= self.bad_temp:
			t_pixels.extend([self.WARN_PIXEL] * t_on_count)
		else:
			t_pixels.extend([self.BAD_PIXEL] * t_on_count)
		
		t_pixels.extend([self.OFF_PIXEL] * t_off_count)
		
		if self.temp > self.max_recorded_temp:
			self.max_recorded_temp = self.temp
		
		if self.max_recorded_temp > self.max_temp:
			t_max_count = 16
		elif self.max_recorded_temp < self.min_temp:
			t_max_count = 0
		else:
			norm_max_t = (self.max_recorded_temp-self.min_temp)/(self.max_temp-self.min_temp)
			t_max_count = int(round(16.*norm_max_t))
		for i in range(t_on_count,t_max_count+1):
			t_pixels[i] = self.MAX_PIXEL
		t_pixels = t_pixels[::2] + t_pixels[1::2]
				
		# Humidity Bar
		h_pixels = []
		
		norm_h = self.humidity/100.
		h_on_count = int(round(16.*norm_h))
		h_off_count = 16-h_on_count
		
		if self.humidity <= self.good_humidity:
			h_pixels.extend([self.GOOD_PIXEL] * h_on_count)
		elif self.humidity <= self.bad_humidity:
			h_pixels.extend([self.WARN_PIXEL] * h_on_count)
		else:
			h_pixels.extend([self.BAD_PIXEL] * h_on_count)
		
		h_pixels.extend([self.OFF_PIXEL] * h_off_count)
		
		if self.humidity > self.max_recorded_humidity:
			self.max_recorded_humidity = self.humidity
		norm_max_h = self.max_recorded_humidity/100.
		h_max_count = int(round(16.*norm_max_h))
		for i in range(h_on_count,h_max_count+1):
			h_pixels[i] = self.MAX_PIXEL
		
		h_pixels = h_pixels[::2] + h_pixels[1::2]
		
		pixels = []
		
		pixels.extend([self.OFF_PIXEL for i in range(8)])
		pixels.extend(t_pixels)
		pixels.extend([self.OFF_PIXEL for i in range(8)])
		pixels.extend([self.OFF_PIXEL for i in range(8)])
		pixels.extend(h_pixels)
		pixels.extend([self.OFF_PIXEL for i in range(8)])
		
		self.set_pixels(pixels)

	def alert(self,avgtemp,avghumid):
		self.set_rotation(0)
		msg = ""
		if avgtemp > self.bad_temp:
			msg += " TEMP: {}C".format(round(avgtemp,0))
		if avghumid > self.bad_humidity:
			msg += " HUMID: {}%".format(round(avghumid,0))
		if msg != "":
			self.show_message("ALERT! {}".format(msg),text_colour=self.ALERT_PIXEL)

class AttachmentHandler(emdash.handlers.FileHandler):

    def upload(self):
		target = self.target or self.data.get('_target')
		rec = {}
		rec['_format'] = 'json'
		rec['ctxid'] = emdash.config.get('ctxid')
		rec[self.param] = emdash.transport.UploadFile(self.name,'rb')
		rec = self._upload_put('/record/%s/edit'%(target),rec)
		return rec

if __name__ == "__main__":
	try:
		main()
	except:
		os.execv(EXECUTABLE,sys.argv)
