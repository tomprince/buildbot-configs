#!/usr/bin/python
import sys, re, os

test_header_re = re.compile("==========> TESTING (.*) <==========")
test_trailer_re = re.compile("==========> (.*) <==========")

def parse_log_file(name):
	file = open(name)
	line = file.readline()
	match = test_header_re.match(line)
	if match:
		test = match.group(1)
	else:
		return
	print "test: %s" % (test,)

	lines = []
	for line in file:
		match = test_trailer_re.match(line)
		if match:
			result = match.group(1)
			break
		elif line.startswith("Welcome to Coq") or line.startswith("Skipping rcfile loading."):
			continue
		else:
			lines += [ line ]
	
	if result == "SUCCESS":
		print "success: %s [" % (test,)
	elif result == "FAILURE":
		print "failure: %s [" % (test,)
	print "".join(lines), "]"

for root, dirs, files in os.walk('.'):
	for file in files:
		if file.endswith(".log"):
			parse_log_file(os.path.join(root, file))
