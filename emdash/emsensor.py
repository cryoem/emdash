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
	
	db = config.db()
	logged_in = False
	while logged_in is False:
		try:
			print("LOGGING IN")
			ctxid = db.login(config.get("username"),config.get("password"))
			logged_in = True
		except:
			print("LOG IN FAILED. Will try again in 5 seconds")
			logged_in = False
			time.sleep(5)
		sys.stdout.flush()
	
	print("SUCCESS.")
	emdash.config.set("ctxid",ctxid)
	print("CTXID: {}".format(ctxid))
	
	suite = db.record.get(config.get("suite"))
	print("Record #{}".format(config.get("suite")))
	print("Name: {}".format(suite["suite_name"]))
	
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
				#rec = log.upload(db) ## DEBUG
				samples = []
				last["minute"] = this.minute
			
			# Every hour
			if this.hour != last["hour"]:
				readout = log.read()
				sofar = np.mean(readout,axis=0)
				if sofar[0] > high_temp:
					sense.high_temp_alert(sofar[0] )
				if sofar[1] > high_humid:
					sense.high_humid_alert(sofar[1])
				last["hour"] = this.hour
			
			# Every day
			if this.day != last["day"]:
				rec = log.upload(db)
				sense.reset_maxima()
				last["day"] = this.day
			
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
		suite = db.record.get(config.get("suite"))
		
		rec = {}
		rec['parents'] = suite['name']
		rec['groups'] = suite['groups']
		rec['permissions'] = suite['permissions']
		rec['rectype'] = config.get("session_protocol")
		rec["date_start_dt"] = self.start_date.isoformat()
		rec["date_end_dt"] = self.end_date.isoformat()
		rec["temperature_ambient_low"] = round(t_low,1)
		rec["temperature_ambient_high"] = round(t_high,1)
		rec["temperature_ambient_avg"] = round(t_avg,1)
		rec["humidity_ambient_low"] = round(h_low,1)
		rec["humidity_ambient_high_float"] = round(h_high,1)
		rec["humidity_ambient_avg"] = round(h_avg,1)
		rec["pressure_ambient_low"] = round(p_low,1)
		rec["pressure_ambient_high"] = round(p_high,1)
		rec["pressure_ambient_avg"] = round(p_avg,1)
		rec["comments"] = ""
		
		record = db.record.put(rec)
		
		self.ah.target = record["name"]
		#self.ah.data = record
		
		#try:
		record = self.ah.upload()
		#except:
		#print("Failed to upload {}".format(self.ah.name))
		
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

	ON_H_PIXEL=[0,0,255]
	ON_T_PIXEL=[255,0,0]
	READ_PIXEL=[255,255,255]
	OFF_PIXEL=[0,0,0]
	
	max_recorded_temp = 0.
	max_recorded_humidity = 0.
	
	max_temp = 37.7 # temperature at which all LEDs will be displayed
	
	def get_environment(self,rnd=1):
		T = round(self.temperature,rnd)
		H = round(self.humidity,rnd)
		P = round(self.pressure,rnd)
		return [T,H,P]
	
	def reset_maxima(self):
		self.max_recorded_humidity = 0.
		self.max_recorded_temperature = 0.
	
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
		
		h_pixels = []
		h_on_count = int(32*(self.humidity/100.))
		h_off_count = 32-h_on_count
		h_pixels.extend([self.ON_H_PIXEL] * h_on_count)
		h_pixels.extend([self.OFF_PIXEL] * h_off_count)
		
		if self.humidity > self.max_recorded_humidity:
			self.max_recorded_humidity = self.humidity
		
		h_max_pixel = int(32*(self.max_recorded_humidity / 100.))
		h_pixels[h_max_pixel] = self.READ_PIXEL
		
		t_pixels = []
		if self.temp > self.max_temp:
			t_on_count = 32
		elif self.temp < 0:
			t_on_count = 0
		else:
			t_on_count = int(32*(self.temp/self.max_temp))
		t_off_count = 32-t_on_count
		t_pixels.extend([self.ON_T_PIXEL] * t_on_count)
		t_pixels.extend([self.OFF_PIXEL] * t_off_count)
		
		if self.temp > self.max_recorded_temp:
			self.max_recorded_temp = self.temp
		
		t_max_pixel = int(32*(self.max_recorded_temp / self.max_temp))
		t_pixels[t_max_pixel] = self.READ_PIXEL
		
		pixels = []
		pixels.extend(h_pixels)
		pixels.extend(t_pixels)
		
		self.set_pixels(pixels)

	def high_humid_alert(self,value):
		self.set_rotation(0)
		self.show_message("ALERT!")
		self.show_message("HIGH HUMIDITY: {:0.0f}%".format(value),text_colour=self.ON_H_PIXEL)

	def high_temp_alert(self,value):
		self.set_rotation(0)
		self.show_message("ALERT!")
		self.show_message("HIGH TEMP: {:0.0f}C".format(value),text_colour=self.ON_T_PIXEL)

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
