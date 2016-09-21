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

	samples = []
	
	daily_temps = []
	daily_humids = []

	log = EMSensorLog(config)
	
	try:
		while True:
			this = gettime()
			
			# Every second
			if this.second != last["second"]:
				data = sense.get_environment()
				samples.append(data)
				daily_temps.append(data[0])
				daily_humids.append(data[1])
				sense.avg_rec_temp = np.mean(daily_temps)
				sense.avg_rec_humid = np.mean(daily_humids)
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
				sense.reset_meta()
				daily_temps = []
				daily_humids = []
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
	MAX_PIXEL = [50,50,50]
	AVG_PIXEL = [50,0,50]
	LOW_PIXEL = [0,100,100]
	GOOD_PIXEL = [0,100,0]
	WARN_PIXEL = [100,100,0]
	BAD_PIXEL = [100,0,0]
	ALERT_PIXEL = [255,255,255]
	
	pix_grad = [LOW_PIXEL,GOOD_PIXEL,WARN_PIXEL,BAD_PIXEL,BAD_PIXEL]

	bar_npix = 16

	max_temp = 26.0
	min_temp = 15.0
	temp_range = max_temp-min_temp
	
	good_temp = 18.0
	warn_temp = 21.5
	bad_temp = 22.0
	
	t_weights = []
	t_weights.append(int(bar_npix*(good_temp-min_temp)/temp_range))
	t_weights.append(int(bar_npix*(warn_temp-min_temp)/temp_range)-sum(t_weights)-1)
	t_weights.append(int(bar_npix*(bad_temp-min_temp)/temp_range)-sum(t_weights)+3)
	t_weights.append(bar_npix-sum(t_weights))
	t_weights.append(1) # dummy
	
	max_rec_temp = 0.
	min_rec_temp = 100.
	avg_rec_temp = 0.
	
	good_humidity = 20.0
	warn_humidity = 31.0
	bad_humidity = 32.0
	
	max_humid = 50.0
	min_humid = 0.0
	humid_range = max_humid - min_humid
	
	h_weights = []
	h_weights.append(int(bar_npix*(good_humidity-min_humid)/humid_range))
	h_weights.append(int(bar_npix*(warn_humidity-min_humid)/humid_range)-sum(h_weights)-1)
	h_weights.append(int(bar_npix*(bad_humidity-min_humid)/humid_range)-sum(h_weights)+3)
	h_weights.append(bar_npix-sum(h_weights))
	h_weights.append(1) # dummy
	
	max_rec_humid = 0.
	min_rec_humid = 100.
	avg_rec_humid = 0.
	
	def get_environment(self,rnd=1):
		T = round(self.temperature,rnd)
		H = round(self.humidity,rnd)
		P = round(self.pressure,rnd)
		return [T,H,P]
	
	def reset_meta(self):
		self.max_rec_humid = 0.
		self.max_rec_temp = 0.
		self.min_rec_temp = 100000.
		self.min_rec_humid = 100000.
		self.avg_rec_temp = 0.
		self.avg_rec_humid = 0.
	
	def update_avg(self,avgt,avgh):
		self.avg_rec_temp = avgt
		self.avg_rec_humid = avgh
	
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
			t_on_count = self.bar_npix
		elif self.temp < self.min_temp:
			t_on_count = 0
		else:
			norm_t = (self.temp-self.min_temp)/self.temp_range
			t_on_count = int(self.bar_npix*norm_t)
		
		t_off_count = self.bar_npix-t_on_count
		
		t_grad = self.polylinear_color_gradient(self.pix_grad,self.t_weights)
		t_pixels.extend(t_grad[:t_on_count])
		
		t_pixels.extend([self.OFF_PIXEL] * t_off_count)
		
		t_pixels = t_pixels[::2] + t_pixels[1::2]
		
		if self.temp > self.max_rec_temp:
			self.max_rec_temp = self.temp
		
		if self.temp < self.min_rec_temp:
			self.min_rec_temp = self.temp

		#t_meta_col = []
		
		#if self.max_rec_temp > self.max_temp:
			#max_t_on_count = self.bar_npix/2
		#elif self.max_rec_temp < self.min_temp:
			#max_t_on_count = 0
		#else:
			#max_t_on_count = int((self.bar_npix/2)*(self.max_rec_humid-self.min_humid)/self.humid_range)
		
		#t_meta_col.extend([self.MAX_PIXEL for i in range(max_t_on_count)])
		#max_t_off_count = (self.bar_npix/2) - max_t_on_count
		#t_meta_col.extend([self.OFF_PIXEL for i in range(max_t_off_count)])
		
		#if self.min_rec_temp > self.min_temp and self.min_rec_temp < self.max_temp:
			#min_t_idx = int((self.bar_npix/2)*(self.min_rec_temp-self.min_temp)/self.temp_range)
			#for i in range(min_t_idx):
				#t_meta_col[i] = self.OFF_PIXEL
		
		#if self.avg_rec_temp > self.max_temp:
			#t_meta_col[-1] = self.AVG_PIXEL
		#elif self.avg_rec_temp < self.min_temp:
			#t_meta_col[0] = self.AVG_PIXEL
		#else:
			#avg_t_idx = int((self.bar_npix/2)*(self.avg_rec_temp-self.min_temp)/self.temp_range)
			#t_meta_col[avg_t_idx] = self.AVG_PIXEL

		# Humidity Bar
		h_pixels = []
		
		if self.humidity >= self.max_humid:
			h_on_count = self.bar_npix
		elif self.humidity < self.min_humid:
			h_on_count = 0
		else:
			norm_h = (self.humidity-self.min_humid)/self.humid_range
			h_on_count = int(self.bar_npix*norm_h)
		
		h_grad = self.polylinear_color_gradient(self.pix_grad,self.h_weights)
		h_pixels.extend(h_grad[:h_on_count])
		
		h_off_count = self.bar_npix-h_on_count
		h_pixels.extend([self.OFF_PIXEL] * h_off_count)
		
		h_pixels = h_pixels[::2] + h_pixels[1::2]

		if self.humidity > self.max_rec_humid:
			self.max_rec_humid = self.humidity
		
		if self.humidity < self.min_rec_humid:
			self.min_rec_humid = self.humidity
		
		#h_meta_col = []
		
		#if self.max_rec_humid > self.max_humid:
			#max_h_on_count = self.bar_npix/2
		#elif self.max_rec_humid < self.min_humid:
			#max_h_on_count = 0
		#else:
			#max_h_on_count = int((self.bar_npix/2)*(self.max_rec_humid-self.min_humid)/self.humid_range)
		
		#h_meta_col.extend([self.MAX_PIXEL for i in range(max_h_on_count)])
		#max_h_off_count = (self.bar_npix/2) - max_h_on_count
		#h_meta_col.extend([self.OFF_PIXEL for i in range(max_h_off_count)])
		
		#if self.min_rec_humid > self.min_humid and self.min_rec_humid < self.max_humid:
			#min_h_idx = int((self.bar_npix/2)*(self.min_rec_humid-self.min_humid)/self.humid_range)
			#for i in range(min_h_idx):
				#h_meta_col[i] = self.OFF_PIXEL
		#else:
			#for i in range(len(h_meta_col)):
				#h_meta_col[i] = self.OFF_PIXEL
		
		#if self.avg_rec_humid > self.min_humid:
			#h_meta_col[-1] = self.AVG_PIXEL
		#elif self.avg_rec_humid < self.max_humid:
			#h_meta_col[0] = self.AVG_PIXEL
		#else:
			#avg_h_idx = int((self.bar_npix/2)*(self.avg_rec_humid-self.min_humid)/self.humid_range)
			#h_meta_col[avg_h_idx] = self.AVG_PIXEL

		pixels = []
		
		pixels.extend([self.OFF_PIXEL for i in range(8)])
		pixels.extend(t_pixels) # 16
		pixels.extend([self.OFF_PIXEL for i in range(8)])
		#pixels.extend(t_meta_col) # 8
		
		pixels.extend([self.OFF_PIXEL for i in range(8)])
		pixels.extend(h_pixels) # 16
		#pixels.extend(h_meta_col) # 8
		pixels.extend([self.OFF_PIXEL for i in range(8)])

		#print(len(pixels),len(h_meta_col),len(t_meta_col),len(t_pixels),len(h_pixels))
		
		self.set_pixels(pixels)

	def alert(self,avgtemp,avghumid):
		self.set_rotation(0)
		msg = ""
		if avghumid > self.bad_humidity:
			msg += ' {}%RH'.format(int(round(avghumid,0)))
		if avgtemp > self.bad_temp:
			msg += ' {}C'.format(int(round(avgtemp,0)))
		if msg != "":
			self.show_message("ALERT! {}".format(msg),text_colour=self.ALERT_PIXEL)

	# Neat discussion of color gradients and source of following code:
	# http://bsou.io/posts/color-gradients-with-python

	def linear_color_gradient(self, s, f, n=16):
		'''
		returns a gradient list of (n) colors between
		two rgb colors (s,f).
		'''
		rgb = [s]
		# Calcuate a color at each evenly spaced value of t from 1 to n
		for t in range(1, n+1):
			# Interpolate RGB vector for color at the current value of t
			curr_vector = [int(s[j] + (float(t)/(n+1-1))*(f[j]-s[j])) for j in range(3)]
			# Add it to our list of output colors
			rgb.append(curr_vector)
		return rgb

	def polylinear_color_gradient(self,colors,wts):
		'''
		returns a list of colors forming linear gradients between
		all sequential pairs of colors. "n" specifies the total
		number of desired output colors
		'''
		pcgrad = []
		for col in range(len(colors)-1):
			lcgrad = self.linear_color_gradient(colors[col], colors[col+1], wts[col])
			pcgrad.extend(lcgrad[1:])
		return pcgrad

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
