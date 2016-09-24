#!/usr/bin/env python

# Author: James Michael Bell, BCM 2016 (jmbell@bcm.edu)

# To find pis on network, I recommend nmap using the following syntax:
# nmap -sP 10.10.0-13.1/24 | grep raspberrypi

from sense_hat import SenseHat, InputEvent
from datetime import datetime
import os
from os.path import getmtime
import sys
import numpy as np
import time
import dateutil
import dateutil.tz

# for IP address
import netifaces as ni


# for button press events
from threading import Thread

# for uploads to ncmidb
import emdash
import emdash.config
import emdash.handlers
#import jsonrpc.proxy

EXECUTABLE = "/usr/local/bin/emdash_environment.py"
WATCHED_FILES = [__file__,EXECUTABLE]
WATCHED_FILES_MTIMES = [(f, getmtime(f)) for f in WATCHED_FILES]

def gettime():
    return datetime.now(dateutil.tz.gettz())

def getipaddr():
	ni.ifaddresses('eth0')
	ip = ni.ifaddresses('eth0')[2][0]['addr']
	return ip

def printout(msg,level="LOG"):
	sys.stdout.write("{}\t{}\t{}\n".format(gettime(),level,msg))
	sys.stdout.flush()

def main():
	ns = emdash.config.setconfig()
	config = emdash.config.Config()

	printout("Logging into {} as {}".format(config.get("host"),config.get("username")))
	logged_in = False
	while logged_in is False:
		try:
			db = config.login(config.get("username"),config.get("password"))
			logged_in = True
			context = db.checkcontext()
			printout("Success! Context ID is {}".format(context[0]))
		except Exception,e:
			printout("Log in failed. ({}). Will try again in 10 seconds.".format(e),level="WARNING")
			logged_in = False
			time.sleep(10)

	room = db.record.get(config.get("room_id"))
	msg = "Creating {} records for {} (Record #{})"
	printout(msg.format(config.get("session_protocol"),room["room_name"],config.get("room_id")))

	sense = EMSenseHat()
	sense.clear()

	sense.stick.direction_up = sense.show_meta # up
	sense.stick.direction_down = sense.show_ipaddr # left
	sense.stick.direction_left = sense.show_meta # down
	sense.stick.direction_right = sense.show_meta # right
	sense.stick.direction_middle = sense.show_meta # push

	this = gettime()

	last = {}
	last["second"] = int(this.second)
	last["minute"] = int(this.minute)
	last["hour"] = int(this.hour)
	last["day"] = int(this.day)

	samples = []

	daily_temps = []
	daily_humids = []

	log = EMSensorLog(config,db)

	threads = []

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
				if not sense.INSIDE_CALLBACK:
					# don't flicker during show_message callback
					sense.update_display()
				last["second"] = this.second

			# Every minute
			if this.minute != last["minute"]:
				avg = np.mean(samples,axis=0)
				log.write(avg)
				if not sense.INSIDE_CALLBACK:
					# don't run alert overtop of other messages
					t = Thread(target=sense.alert_if_bad)
					t.setDaemon(True)
					threads.append(t)
					t.start()
				last["minute"] = this.minute

			# Every day
			if this.day != last["day"]:
				t = Thread(target=log.upload,args=(db,))
				t.setDaemon(True)
				threads.append(t)
				t.start()
				sense.reset_meta()
				log = EMSensorLog(config,db)
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
		for i in range(len(threads)):
			threads[i].join()
		sense.clear()

class EMSensorLog:

	def __init__(self,conf,db):
		room = db.record.get(conf.get("room_id"))
		strname = "-".join(room["room_name"].lower().split(" "))
		self.start_date = gettime()
		self.ah = AttachmentHandler()
		self.ah.name = "/home/pi/logs/{}_{}.csv".format(strname,self.start_date.date())
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
		printout("Uploading...")
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

		uploaded = False
		while uploaded == False:
			try:
				record = db.record.put(rec)
				printout("Record uploaded successfully!")
				proceed = True
			except Exception, e:
				printout("Failed to upload record. Exception: {}".format(e),level="ERROR")
				proceed = False

			if proceed:
				try:
					self.ah.target = record["name"]
					record = self.ah.upload()
					printout("{} was uploaded successfully".format(self.ah.name))
					uploaded = True
				except Exception, e:
					printout("Failed to upload file ({}). Exception: {}".format(self.ah.name,e),level="ERROR")

class EMSenseHat(SenseHat):

	INSIDE_CALLBACK=False

	OFF_PIXEL=[0,0,0]
	MAX_PIXEL = [50,50,50]
	AVG_PIXEL = [50,0,50]
	LOW_PIXEL = [0,100,100]
	GOOD_PIXEL = [0,100,0]
	WARN_PIXEL = [100,100,0]
	BAD_PIXEL = [100,0,0]
	ALERT_PIXEL = [255,255,255]
	SOFT_PIXEL = [128,128,128]

	pix_grad = [LOW_PIXEL,GOOD_PIXEL,WARN_PIXEL,BAD_PIXEL,BAD_PIXEL]

	bar_npix = 16

	max_temp = 30.0
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
	nsamples_temp = 0

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
	nsamples_humid = 0

	scroll = 0.08

	def get_environment(self,rnd=1):
		T = round(self.temperature,rnd)
		H = round(self.humidity,rnd)
		P = round(self.pressure,rnd)
		return [T,H,P]

	def reset_meta(self):
		self.max_rec_humid = 0.
		self.max_rec_temp = 0.
		self.min_rec_temp = 100.
		self.min_rec_humid = 100.
		self.avg_rec_temp = 0.
		self.avg_rec_humid = 0.

	def update_average_temp(self,t_new):
		t_old = self.avg_rec_temp * self.nsamples_temp
		self.nsamples_temp += 1
		self.avg_rec_temp = (t_old + t_new) / self.nsamples_temp

	def update_average_humid(self,h_new):
		h_old = self.avg_rec_humid * self.nsamples_humid
		self.nsamples_humid += 1
		self.avg_rec_humid = (h_old + h_new) / self.nsamples_humid

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
		self.set_rotation(270)

		temp, humid, press = self.get_environment()

		# update temperature meta
		if temp > self.max_rec_temp:
			self.max_rec_temp = temp
		if temp < self.min_rec_temp:
			self.min_rec_temp = temp
		self.update_average_temp(temp)

		# update humidity meta
		if humid > self.max_rec_humid:
			self.max_rec_humid = humid
		if humid < self.min_rec_humid:
			self.min_rec_humid = humid
		self.update_average_humid(humid)

		# Temperature Bar
		t_pixels = []

		if temp >= self.max_temp:
			t_on_count = self.bar_npix
		elif temp < self.min_temp:
			t_on_count = 0
		else:
			norm_t = (temp-self.min_temp)/self.temp_range
			t_on_count = int(self.bar_npix*norm_t)
		t_off_count = self.bar_npix-t_on_count

		t_grad = self.polylinear_color_gradient(self.pix_grad,self.t_weights)
		t_pixels.extend(t_grad[:t_on_count])

		t_pixels.extend([self.OFF_PIXEL] * t_off_count)

		if len(t_pixels) > 16:
			t_pixels = t_pixels[:16]

		t_pixels = t_pixels[::2] + t_pixels[1::2]

		# Humidity Bar
		h_pixels = []

		if humid >= self.max_humid:
			h_on_count = self.bar_npix
		elif humid < self.min_humid:
			h_on_count = 0
		else:
			norm_h = (humid-self.min_humid)/self.humid_range
			h_on_count = int(self.bar_npix*norm_h)
		h_off_count = self.bar_npix-h_on_count

		h_grad = self.polylinear_color_gradient(self.pix_grad,self.h_weights)
		h_pixels.extend(h_grad[:h_on_count])

		h_pixels.extend([self.OFF_PIXEL] * h_off_count)

		if len(h_pixels) > 16:
			h_pixels = h_pixels[:16]

		h_pixels = h_pixels[::2] + h_pixels[1::2]

		pixels = []

		pixels.extend([self.OFF_PIXEL for i in range(8)])
		pixels.extend(t_pixels)
		pixels.extend([self.OFF_PIXEL for i in range(8)])
		pixels.extend([self.OFF_PIXEL for i in range(8)])
		pixels.extend(h_pixels)
		pixels.extend([self.OFF_PIXEL for i in range(8)])

		self.set_pixels(pixels)

	def show_meta(self,event):
		if event.action == "pressed":
			if not self.INSIDE_CALLBACK:
				self.show_current(event)
				self.show_average(event)
				self.show_maxima(event)
				self.show_minima(event)

	def show_average(self,event):
		if event.action == "pressed":
			self.INSIDE_CALLBACK = True
			orig_rot = self.rotation
			self.set_rotation(0)
			msg = "AVG: {:.1f}C {:.1f}%H".format(self.avg_rec_temp,self.avg_rec_humid)
			self.show_message(msg,text_colour=self.SOFT_PIXEL,scroll_speed=self.scroll)
			self.set_rotation(orig_rot)
			self.INSIDE_CALLBACK = False

	def show_maxima(self,event):
		if event.action == "pressed":
			self.INSIDE_CALLBACK = True
			orig_rot = self.rotation
			self.set_rotation(0)
			msg = "MAX: {:.1f}C {:.1f}%H".format(self.max_rec_temp,self.max_rec_humid)
			self.show_message(msg,text_colour=self.SOFT_PIXEL,scroll_speed=self.scroll)
			self.set_rotation(orig_rot)
			self.INSIDE_CALLBACK = False

	def show_minima(self,event):
		if event.action == "pressed":
			self.INSIDE_CALLBACK = True
			orig_rot = self.rotation
			self.set_rotation(0)
			msg = "MIN: {:.1f}C {:.1f}%H".format(self.min_rec_temp,self.min_rec_humid)
			self.show_message(msg,text_colour=self.SOFT_PIXEL,scroll_speed=self.scroll)
			self.set_rotation(orig_rot)
			self.INSIDE_CALLBACK = False

	def show_current(self,event):
		if event.action == "pressed":
			self.INSIDE_CALLBACK = True
			orig_rot = self.rotation
			self.set_rotation(0)
			msg = "NOW: {:.1f}C {:.1f}%H".format(self.temp,self.humidity)
			self.show_message(msg,text_colour=self.SOFT_PIXEL,scroll_speed=self.scroll)
			self.set_rotation(orig_rot)
			self.INSIDE_CALLBACK = False

	def show_ipaddr(self,event):
		if event.action == "pressed":
			if not self.INSIDE_CALLBACK:
				self.INSIDE_CALLBACK = True
				orig_rot = self.rotation
				self.set_rotation(0)
				ip = getipaddr()
				self.show_message("IP: {}".format(ip),text_colour=self.SOFT_PIXEL,scroll_speed=self.scroll)
				self.set_rotation(orig_rot)
				self.INSIDE_CALLBACK = False

	def alert_if_bad(self):
		if not self.INSIDE_CALLBACK:
			self.INSIDE_CALLBACK = True
			msg = []
			orig_rot = self.rotation
			self.set_rotation(0)
			if self.temp > self.bad_temp:
				msg.append("{:.1f}C".format(self.temp))
			if self.humidity > self.bad_humidity:
				msg.append("{:.1f}%H".format(self.humidity))
			if len(msg) > 0:
				msg = ["ALERT!"] + msg
				self.show_message(" ".join(msg),text_colour=self.ALERT_PIXEL,scroll_speed=self.scroll)
			self.set_rotation(orig_rot)
			self.INSIDE_CALLBACK = False

	def linear_color_gradient(self, s, f, n=16):
		'''
		returns a gradient list of (n) colors between
		two rgb colors (s,f).
		See http://bsou.io/posts/color-gradients-with-python.
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
