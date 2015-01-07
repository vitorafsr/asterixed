#!/usr/bin/env python

import unittest
import asterix

class TestSimple(unittest.TestCase):

	def setUp(self):
		asterix.verbose = 2

	def test_cat1di10(self):
		atx = {1:{10:{'SAC':1,'SIC':2}}}
		bin = asterix.encode(atx)

		self.assertTrue(bin == 0x010006800102)

	def test_cat1di20(self):
		atx = {1:{20:{'TYP':1,'SIM':1,'SSRPSR':3,'ANT':1,'SPI':0,'RAB':1}}}
		bin = asterix.encode(atx)

		self.assertTrue(bin == 0x01000540fa)

		# observe that FX field fill is auto; not necessary to explicit it
		atx = {1:{20:{'TYP':1,'SIM':1,'SSRPSR':3,'ANT':1,'SPI':0,'RAB':1,'TST':1,'DS1DS2':3,'ME':1,'MI':1}}}
		bin = asterix.encode(atx)

		self.assertTrue(bin == 0x01000640fbf8)


	def test_cat1di30(self):
		atx = {1:{30:{'WE':110}}}
		bin = asterix.encode(atx)

		self.assertTrue(bin == 0x10007010108dc)

if __name__ == '__main__':
	unittest.main()
