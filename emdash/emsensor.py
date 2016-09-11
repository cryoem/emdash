#!/usr/bin/env python

from sense_hat import SenseHat
from datetime import datetime
import os
import numpy as np
import time
import emdash.config

def main():
	config = emdash.config.Config()
	
	print("Host: {}".format(config.get("host")))
	print("User: pi@raspberrypi")
	print("Protocol: {}".format(config.get("session_protocol")))
	
	username = config.get("username")
	password = config.get("password")
	
	db = config.login(username,password) # generic raspberry pi login
	suite = db.record.get(config.get("suite"))
	
	print("Record #{} ({})".format(config.get("suite"),suite["suite_name"]))
	
	sense = EMSenseHat()
	sense.clear()

	this = datetime.now()
	last = {}
	last["second"] = int(this.second)
	last["minute"] = int(this.minute)
	last["hour"] = int(this.hour)
	last["day"] = int(this.day)

	high_temp = 25.  # alert if temperature > this
	high_humid = 45. # alert if humidity > this

	samples = []

	fn = "/home/pi/logs/{}.csv".format(this.date())
	log = EMSensorLog(fn)
	
	while True:
		this = datetime.now()
		data = sense.readout()
		samples.append(data)
		
		# Every second
		if this.second != last["second"]:
			sense.update_display()
			time.sleep(1)
		
		# Every minute
		if this.minute != last["minute"]:
			avg = np.mean(samples,axis=0)
			log.write(avg)
			last["minute"] = this.minute
			to_average = []
		
		# Every hour
		if this.hour != last["hour"] and this.hour != 0:
			record = log.upload(db)
			if record["temperature_ambient_avg"] > high_temp:
				sense.high_temp_alert(record["temperature_ambient_avg"])
			if record["humidity_ambient_avg"] > high_humid:
				sense.high_humid_alert(record["humidity_ambient_avg"])
			
			try: os.unlink(fn)
			except: print("Failed to unlink {}".format(fn))
			
			fn = "/home/pi/logs/{}.csv".format(this.date())
			log = EMSensorLog(fn) # create new log
			
			last["hour"] = this.hour
		
		# Every day
		if this.day != last["day"]:
			last["day"] = this.day

class EMSensorLog:

	def __init__(self,filename):
		self.filename = filename
		header = ["timestamp","temperature","humidity","pressure"]
		if not os.path.isfile(self.filename):
			with open(self.filename,"w") as f:
				f.write("#{}\n".format(",".join(header)))
	
	def write(self,data,rnd=1):
		n = datetime.now()
		tstamp = "{} {}:{:02}".format(n.date(),n.hour,n.minute)
		with open(self.filename,"a") as f:
			dat = ",".join([str(round(val,rnd)) for val in data])
			out = "{},{}\n".format(tstamp,dat)
			f.write(out)
	
	def read(self):
		data = []
		with open(self.filename,"r") as f:
			for i,l in enumerate(f):
				if i > 0: # skip header
					line = l.strip().split(",")
					if i == 1: self.start_date = line[0]
					data.append(line[1:])
			self.end_date = line[0]
		return np.asarray(data).astype(float)
	
	def upload(self,db):
		data = self.read()
		t_high,h_high,p_high = np.max(data,axis=0)
		t_low,h_low,p_low = np.min(data,axis=0)
		t_avg,h_avg,p_avg = np.mean(data,axis=0)
		
		suite = db.record.get(config.get("suite"))
		
		rec = {}
		rec['parents'] = suite['name']
		rec['groups'] = suite['groups']
		rec['permissions'] = suite['permissions']
		rec['rectype'] = config.get("session_protocol")
		rec["date_start_str"] = str(self.start_date)
		rec["date_end_str"] = str(self.end_date)
		rec["temperature_ambient_low"] = round(t_low,1)
		rec["temperature_ambient_high"] = round(t_high,1)
		rec["temperature_ambient_avg"] = round(t_avg,1)
		rec["humidity_ambient_low"] = round(h_low,1)
		rec["humidity_ambient_high_float"] = round(h_high,1)
		rec["humidity_ambient_avg"] = round(h_avg,1)
		rec["pressure_ambient_low"] = round(p_low,1)
		rec["pressure_ambient_high"] = round(p_high,1)
		rec["pressure_ambient_avg"] = round(p_avg,1)
		rec["comments"] = "testing"
		
		record = db.record.put(rec)
		return record

class EMSenseHat(SenseHat):

	ON_H_PIXEL=[0,0,125]
	ON_T_PIXEL=[125,0,0]
	OFF_PIXEL=[0,0,0]

	high_temp = 37.7
	low_temp = 0.

	def readout(self,rnd=1):
		T = round(self.temperature,rnd)
		H = round(self.humidity,rnd)
		P = round(self.pressure,rnd)
		return [T,H,P]

	def update_display(self):
		pixels = []
		h_on_count = int(32*(self.humidity/100.))
		h_off_count = 32-h_on_count
		pixels.extend([self.ON_H_PIXEL] * h_on_count)
		pixels.extend([self.OFF_PIXEL] * h_off_count)
		norm_temp = (self.high_temp-self.temp)/(self.high_temp-self.low_temp)
		t_on_count = int(32*(norm_temp))
		t_off_count = 32-t_on_count
		pixels.extend([self.ON_T_PIXEL] * t_on_count)
		pixels.extend([self.OFF_PIXEL] * t_off_count)
		self.set_pixels(pixels)

	def high_humid_alert(self,value):
		self.show_message("ALERT!")
		self.show_message("HIGH HUMIDITY: {:0.0f}%".format(value),text_colour=self.ON_H_PIXEL)

	def high_temp_alert(self,value):
		self.show_message("ALERT!")
		self.show_message("HIGH TEMP: {:0.0f}C".format(value),text_colour=self.ON_T_PIXEL)

if __name__ == "__main__":
	main()
