#!/usr/bin/env python
# -*- coding: utf-8 -*-

# $Id$

#
# Under GNU General Public License
#
# Author:   Cesar Alcalde
# Email:    lambda512@gmail.com
# JabberID: lambda512@jabberes.com
#


# TODO: Make the code prettier, pylint

from ConfigParser import SafeConfigParser, NoOptionError
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import os
from os.path import abspath, dirname, isabs, join
try:
	import cPickle as pickle
except ImportError:
	import pickle
import sys
import urllib
try:
	import xml.etree.cElementTree as ET
except ImportError:
	import xml.etree.ElementTree as ET

# Load the logging configuration and configure the logger
SCRIPT_DIR = abspath(dirname(sys.argv[0]))
cfg = SafeConfigParser()
cfg.readfp(open(join(SCRIPT_DIR, 'config.cfg')))

try:
	LOGFILE         = cfg.get("Logs", "LOGFILE")
except NoOptionError:
	LOGFILE         = None
	logging.basicConfig(
#	    level=logging.WARNING,
	    level=logging.DEBUG,
	    format='%(asctime)s %(levelname)s %(message)s'
	    )
else:
	if not isabs(LOGFILE):
		LOGFILE = join(SCRIPT_DIR, LOGFILE)
	if os.access(LOGFILE, os.F_OK):
		do_rollover = True
	else:
		do_rollover = False
	logger = logging.getLogger()
	logger.setLevel(logging.DEBUG)
	handler = RotatingFileHandler(LOGFILE, backupCount=10)
	handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
	if do_rollover:
		handler.doRollover()
	logger.addHandler(handler)

# Now import our modules (some use logging)

try:
	from include.ipv6_aux import is_ipv6_ready
except ImportError:
	CHECK_IPv6 = False
else:
	CHECK_IPv6 = True

try:
	from MySQLdb import MySQLError
	from include import database_updater
except ImportError:
	CAN_UPDATE_DATABASE = False
else:
	CAN_UPDATE_DATABASE = True

from include import xmpp_discoverer
from include.helpers import get_version
from include import html_file_generator, xml_file_generator


# Load the rest of the configuration


# Misc
UPTIME_LOG_DAYS     = cfg.getint("Misc", "UPTIME_LOG_DAYS")

# Database
DBUSER              = cfg.get("Database", "USER")
DBPASSWORD          = cfg.get("Database", "PASSWORD")
DBHOST              = cfg.get("Database", "HOST")
DBDATABASE          = cfg.get("Database", "DATABASE")

UPDATE_DATABASE     = cfg.getboolean("Database", "UPDATE_DATABASE")

# Output configuration
OUTPUT_DIRECTORY    = cfg.get("Output configuration", "OUTPUT_DIRECTORY")

GENERATE_HTML_FILES = cfg.getboolean("Output configuration", "GENERATE_HTML_FILES")
GENERATE_XML_FILES  = cfg.getboolean("Output configuration", "GENERATE_XML_FILES")
COMPRESS_FILES      = cfg.getboolean("Output configuration", "COMPRESS_FILES")

HTML_UPTIME_FILTER   = cfg.getfloat("Output configuration", "HTML_UPTIME_FILTER")
XML_UPTIME_FILTER   = cfg.getfloat("Output configuration", "XML_UPTIME_FILTER")

HTML_FILES_PREFIX   = cfg.get("Output configuration", "HTML_FILES_PREFIX")
XML_FILENAME        = cfg.get("Output configuration", "XML_FILENAME")



# TODO: Add compatibility with old config
#
# Configuration used to be:
# [Server list]
# USE_URL             = True
# USE_FILE            = True
# SERVERS_URL         = http://xmpp.org/services/services.xml
# SERVERS_FILE        = serverlist.xml
#
# Now we add any setting wich starts with "SERVERS_URL"
#
#

# Server list
USE_URLS            = cfg.getboolean("Server list", "USE_URL")
USE_FILE            = cfg.getboolean("Server list", "USE_FILE")
#SERVERS_URL         = cfg.get("Server list", "SERVERS_URL")

# I add some sources by default, feel free to comment them
SERVERS_URLS = set( (
	"http://xmpp.org/services/services.xml",
	"http://xmpp.org/services/services-full.xml",
	"https://list.jabber.at/api/?format=services-full.xml"
) )

for option in cfg.options("Server list"):
	if option.upper().startswith("SERVERS_URL"):
		SERVERS_URLS.add(cfg.get("Server list", option))



#SERVERS_FILE       = "servers-fixed.xml"
SERVERS_FILE        = cfg.get("Server list", "SERVERS_FILE")



# Debug
# If false, load the discovery results from servers.dump file,
# instead waiting while doing the real discovery
DO_DISCOVERY        = cfg.getboolean("Debug", "DO_DISCOVERY")

del(cfg)
# Configuration loaded




if not isabs(SERVERS_FILE):
	SERVERS_FILE = join(SCRIPT_DIR, SERVERS_FILE)

if not isabs(OUTPUT_DIRECTORY):
	OUTPUT_DIRECTORY = join(SCRIPT_DIR, OUTPUT_DIRECTORY)

XML_FILE = join(OUTPUT_DIRECTORY, XML_FILENAME)

SERVERS_DUMP_FILE = join(SCRIPT_DIR, 'servers.dump')


logging.info('Starting execution of XMPP Server Scanner %s' % get_version())

if DO_DISCOVERY:
	# Get server list

	try:
		if USE_FILE:
			server_data = dict()
			f = open(SERVERS_FILE, 'r')
			tree = ET.parse(f)
			file_servers = [item.get('jid') for item in tree.getroot().getchildren()]
			f.close()

		if USE_URLS:
			server_data = dict()
			for url in SERVERS_URLS:
				f = urllib.urlopen(url)
				tree = ET.parse(f)
				f.close()

				#tmp_url_servers = [item.get('jid') for item in tree.findall("/item")]

				tmp_server_data = dict((item.get('jid'), dict((element.tag, element.text) for element in item.getchildren() if element.text is not None)) for item in tree.findall("./item"))

				for jid in tmp_server_data.iterkeys():
					if jid in server_data:
						# This server was already on the list, combine the data
						for item in tmp_server_data[jid].iterkeys():
							assert tmp_server_data[jid][item] is not None

							if item in server_data[jid]:
								# The field (homepage, description... is in both lists

								if len(server_data[jid][item]) < len(tmp_server_data[jid][item]):
									server_data[jid][item] = tmp_server_data[jid][item]
							else:
								server_data[jid][item] = tmp_server_data[jid][item]
					else:
						server_data[jid] = tmp_server_data[jid] #dict((k, v) for k, v in tmp_server_data[jid].iteritems() if v is not None)

			url_servers = list(server_data.iterkeys())

	except IOError:
		logging.critical('The server list can not be loaded', exc_info=sys.exc_info())
		raise

	if USE_URLS and USE_FILE:
		server_list = set(url_servers + file_servers)
	elif USE_FILE:
		server_list = set(file_servers)
	elif USE_URLS:
		server_list = set(url_servers)
	else:
		logging.critical('You must configure the script to load the server list from the file, the url, or both')
		raise Exception('You must configure the script to load the server list from the file, the url, or both')

	assert "description" not in server_list and "homepage" not in server_list

	#server_list=['jabberes.org', 'jab.undernet.cz', '12jabber.com', 'allchitchat.com', 'jabber.dk', 'amessage.be', 'jabber-hispano.org', 'example.net']
	#server_list=['jabberes.org']
	#server_list=['swissjabber.ch','default.co.yu','chrome.pl','codingteam.net','coruscant.info','core.segfault.pl','deshalbfrei.org','zweilicht.org','volgograd.ru','silper.cz','kingshomeworld.com','jabjab.de']

	if len(server_list) == 0:
		logging.critical('The list of servers to check is empty')
		raise Exception('The list of servers to check is empty')

	servers = xmpp_discoverer.discover_servers(server_list)
	#servers = {k : {'jid': k, 'available': False, 'available_services': {}, 'unavailable_services': {}} for k in server_list}
	#from pprint import pprint
	#pprint(servers)

	# Add extra data to the servers dictionary
	for server in servers:
		if server in server_data:
			servers[server]['about'] = server_data[server]

	if CHECK_IPv6:
		for jid, server in servers.iteritems():
			if server['available']:
				server['ipv6_ready'] = is_ipv6_ready(jid)

	# Manage offline servers and stability information

	#offline = lambda server: len(server[u'info'][0]) == 0 and len(server[u'info'][1]) == 0
	offline = lambda server: not server['available']
	now = datetime.utcnow()
	uptime_log_days = timedelta(UPTIME_LOG_DAYS)

	try:
		f = open(SERVERS_DUMP_FILE, 'rb')
		old_servers = pickle.load(f)
		f.close()

	except IOError:
		logging.warning( "Error loading servers data in file %s. Is the script executed for first time?" % SERVERS_DUMP_FILE,
		                 exc_info=sys.exc_info() )
		for server in servers.itervalues():
			if offline(server):
				server['offline_since'] = now
				server['uptime_data'] = {now: False}
				server['times_queried_online'] = 0
				server['times_queried'] = 1
			else:
				server['offline_since'] = None
				server['uptime_data'] = {now: True}
				server['times_queried_online'] = 1
				server['times_queried'] = 1

	else:
		for jid, server in servers.iteritems():
			if offline(server):
				try:
					servers[jid] = old_servers[jid]
					server = servers[jid]
					if server['offline_since'] is None:
						server['offline_since'] = now
					server['uptime_data'][now] = False
					logging.warning("%s server seems to be offline, using old data", jid)
				except KeyError: # It's a new server
					logging.debug("Initializing stability data for %s", jid)
					server['uptime_data'] = {now: False}
					server['offline_since'] = now
			else:
				server['offline_since'] = None
				try:
					server['uptime_data'] = old_servers[jid]['uptime_data']
					server['uptime_data'][now] = True
				except KeyError: # It's a new server
					logging.debug("Initializing stability data for %s", jid)
					server['uptime_data'] = {now: True}

			# Delete old uptime information

			for log_date in sorted(server['uptime_data']):
				if (now - log_date) > uptime_log_days:
					del(server['uptime_data'][log_date])
				else:
					break

			#Recalculate times_queried_online and times_queried

			server['times_queried_online'] = server['uptime_data'].values().count(True)
			server['times_queried'] = len(server['uptime_data'])

	finally:
		try:
			f = open(SERVERS_DUMP_FILE, 'wb')
			pickle.dump(servers, f, -1)
			f.close()
		except IOError:
			logging.error("Error saving servers data in %s" % SERVERS_DUMP_FILE)
else:
	try:
		logging.warning("Skiping discovery proccess. Will use the data stored in %s file." % SERVERS_DUMP_FILE,
		             exc_info=sys.exc_info())
		f = open(SERVERS_DUMP_FILE, 'rb')
		servers = pickle.load(f)
		f.close()
	except IOError:
		logging.critical("Error loading servers data from file %s" % SERVERS_DUMP_FILE,
		                 exc_info=sys.exc_info())
		raise

# Now dump the information to the database

if UPDATE_DATABASE and not CAN_UPDATE_DATABASE:
	logging.critical("Can't update the database. Is MySQLdb module available?")
elif UPDATE_DATABASE and CAN_UPDATE_DATABASE:
	try:
		database_updater.update_database( DBUSER, DBPASSWORD, DBHOST,
		                                  DBDATABASE, servers )
	except MySQLError:
		# TODO: database_updater should raise a custom exception
		logging.critical("Can't update the database.", exc_info=sys.exc_info())


# And build the HTML pages and the XML

# Take a look to the XMPP Registrar to see the component's category:type
# http://www.xmpp.org/registrar/disco-categories.html
# Pure MUC components are marked as x-muc by the xmpp_discoverer
show_types = [ ('conference','x-muc'), ('conference','irc'),
               ('gateway', 'gadu-gadu'),
               ('gateway', 'gtalk'), ('gateway', 'icq'),
               ('gateway', 'sms'), ('gateway', 'smtp'),
               ('gateway', 'xmpp'),
	       ('gateway', 'twitter'), ('gateway', 'facebook'), ('gateway', 'whatsapp'),
	       ('gateway', 'telegram'), ('gateway', 'skype'),
               ('directory', 'user'), ('pubsub', 'pep'),
               ('store', 'file'),
               ('headline', 'newmail'),
               ('proxy', 'bytestreams') ]
# Old types
# ('gateway', 'aim'), ('gateway', 'msn'), ('gateway', 'qq'), ('gateway', 'tlen'), ('gateway', 'yahoo'),
# ('component', 'presence'), ('headline', 'rss'), ('headline', 'weather'),

if GENERATE_HTML_FILES:
	html_file_generator.generate_all( directory=OUTPUT_DIRECTORY,
	                                  filename_prefix=HTML_FILES_PREFIX,
	                                  servers=servers, types=show_types,
	                                  minimun_uptime=HTML_UPTIME_FILTER,
	                                  compress=COMPRESS_FILES )

if GENERATE_XML_FILES:
	xml_file_generator.generate(XML_FILE, servers, minimun_uptime=XML_UPTIME_FILTER)
