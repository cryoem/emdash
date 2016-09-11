#!/usr/bin/env python

from sense_hat import SenseHat
from datetime import datetime
import os
import numpy as np
import time

def main():
	sense = EMSenseHat()
	sense.clear()

	this = datetime.now()
	last = {}
	last["second"] = int(this.second)
	last["minute"] = int(this.minute)
	last["hour"] = int(this.hour)
	last["day"] = int(this.day)

	high_temp = 25  # alert if temperature > this
	high_humid = 45 # alert if humidity > this

	samples = []

	fn = "/home/pi/SuiteLogs/{}.csv".format(this.date())
	log = EMSensorLog(fn)
	
	while True:
		this = datetime.now()
		data = sense.readout()
		samples.append(data)

		if int(this.minute) != last["minute"]:
			avg = np.mean(samples,axis=0)
			log.write(avg)

			last["minute"] = int(this.minute)
			to_average = []

			if avg[0] > high_temp:
				sense.high_temp_alert(avg[0])
			if avg[1] > high_humid:
				sense.high_humid_alert(avg[1])
		
		if this.second != last["second"]:
			sense.update_display()
			time.sleep(0.5)

		if int(this.day) != last["day"]:
			log.upload()
			#os.unlink(self.filename)
			fn = "/home/pi/SenseLogs/{}.csv".format(this.date())
			log = EMSensorLog(fn) # create new log
			last["day"] = int(this.day)


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
	
	def upload(self):
		data = []
		with open(self.filename,"r") as f:
			for i,l in enumerate(f):
				if i > 0: # skip header
					line = l.strip().split(",")
					if i == 1:
						start = line[0]
					data.append(line[1:])
			end = line[0]
		data = np.asarray(data).astype(float)
		t_high,h_high,p_high = np.max(data,axis=0)
		t_low,h_low,p_low = np.min(data,axis=0)
		t_avg,h_avg,p_avg = np.mean(data,axis=0)
		
		params = {}
		params["date_start"] = start
		params["date_end"] = end
		params["temperature_ambient_low"] = round(t_low,1)
		params["temperature_ambient_high"] = round(t_high,1)
		params["temperature_ambient_avg"] = round(t_avg,1)
		params["humidity_ambient_low"] = round(h_low,1)
		params["humidity_ambient_high"] = round(h_high,1)
		params["humidity_ambient_avg"] = round(h_avg,1)
		params["pressure_ambient_low"] = round(p_low,1)
		params["pressure_ambient_high"] = round(p_high,1)
		params["pressure_ambient_avg"] = round(p_avg,1)
		params["file_binary"] = self.filename
		
		print(params)

    def add_param(self, param, rectype, value):
        # Add a comment to a known record
        name = self.names.get(rectype, -1)
        if name < 0:
            self.error("Could not add value because there was no %s record yet for this session."%rectype)
            return
        self.set(name, "comments", comment)

class EMSenseHat(SenseHat):

	ON_H_PIXEL=[0,0,125]
	ON_T_PIXEL=[125,0,0]
	OFF_PIXEL=[0,0,0]

	high_temp = 37.7
	low_temp = 0

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
