# -*- coding: utf-8 -*-

# $Id$

#
# Under GNU General Public License
#
# Author:   Cesar Alcalde
# Email:    lambda512@gmail.com
# JabberID: lambda512@jabberes.com
#

# TODO: Make the HTML and the CSS less verbose

"""This module generates html files from the data gathered by the xmpp_discoverer
	There are two functions generate() and generate_all()
	
	generate_all() just generates several html files sorted by columns
	
	The files are static and can be very verbose so, you might want
	to cache and compress them.
	
	You can use dynamic compression or static compression, the dynamic
	compression compreses the page on every request, the static one compress
	the page on the first request and stores it to serve it from that moment.
	
	Since the webpage content doesn't change, you might prefer static
	compression to lower the CPU load.
	
	Just in case your webserver doesn't support static compression, I have
	added the compress option. This option, generates gzipped files, so you can
	serve them specifing the enconding as gzip.
	
	Then you have to configure your server.
	
	
	
	On Apache, static compresion can be achieved combining mod_deflate and
	mod_cache. Or, if they aren't available, generating the gzipped page and
	configuring Apache like:
	
	AddEncoding x-gzip .gz
	<IfModule mod_rewrite.c>
		RewriteEngine On
		RewriteCond %{HTTP:Accept-Encoding} gzip
		RewriteCond %{REQUEST_FILENAME}.gz -f
		RewriteRule ^(.+).html$ $1.$2.gz [L]
	</IfModule>
	
	
	
	On lighttpd, static compression can be achieved using mod_compress or
	generating the gzipped page and configuring lighttpd like:
	
	# Assuming that the pages are on /servers/ and that the index is servers.html.gz
	url.rewrite-once = (
		"^/servers/$" => "/servers/servers.html.gz",
		"^/servers/([a-zA-Z\-_]+)\.html?$" => "/servers/$1.html.gz"
	)
	
	$HTTP["url"] =~ "^/servers/([a-zA-Z_\-]+)\.html(\.gz)?$" {
		compress.filetype          = () # Disable static compression of the already compressed pages
		setenv.add-response-header = ( "Content-Encoding" => "gzip" )
		mimetype.assign = ( ".html.gz" => "text/html" )
	}
	
	
	"""


from ConfigParser import SafeConfigParser
from datetime import datetime, timedelta
from glob import iglob
import gzip
import logging
from os.path import abspath, dirname, basename, join
import shutil
import sys
from xml.sax.saxutils import escape as html_escape
from helpers import get_version

ROWS_BETWEEN_TITLES = 10

# Take a look to the XMPP Registrar to see the component's category:type
# http://www.xmpp.org/registrar/disco-categories.html
COLUMNS_DESCRIPTION = {
  'server': 'Server',
  # Pure MUC components are marked as x-muc by the xmpp_discoverer
  ('conference', 'x-muc'): {'title': 'MUC', 'description': 'MultiUser Chat'},
  ('conference', 'irc'): {'title': 'IRC', 'description': 'Internet Relay Chat Gateway'},
  ('gateway', 'twitter'): {'title': 'Twitter', 'description': 'Twitter Gateway'},
#  ('gateway', 'aim'): {'title': 'AIM', 'description': 'AIM Gateway'},
  ('gateway', 'gadu-gadu'): {'title': 'GG', 'description': 'Gadu Gadu gateway'},
  ('gateway', 'gtalk'): {'title': 'GTalk', 'description': 'Google Talk gateway'},
  ('gateway', 'whatsapp'): {'title': 'WA', 'description': 'WhatsApp gateway'},
#  ('gateway', 'http-ws'): {'title': 'WS', 'description': 'HTTP Web Services'},
  ('gateway', 'icq'): {'title': 'ICQ', 'description': 'ICQ gateway'},
  ('gateway', 'telegram'): {'title': 'Telegram', 'description': 'Telegram gateway'},
#  ('gateway', 'msn'): {'title': 'MSN', 'description': 'MSN gateway'},
#  ('gateway', 'qq'): {'title': 'QQ', 'description': 'QQ gateway'},
  ('gateway', 'sms'): {'title': 'SMS', 'description': 'Short Message Service gateway'},
  ('gateway', 'smtp'): {'title': 'email', 'description': 'SMTP gateway'},
  ('gateway', 'skype'): {'title': 'Skype', 'description': 'Skype gateway'},
#  ('gateway', 'tlen'): {'title': 'TLEN', 'description': 'TLEN gateway'},
  ('gateway', 'xmpp'): {'title': 'XMPP', 'description': 'Jabber/XMPP gateway'},
  ('gateway', 'facebook'): {'title': 'FB', 'description': 'Facebook gateway'},
#  ('gateway', 'yahoo'): {'title': 'Y!', 'description': 'Yahoo! gateway'},
  ('directory', 'user'): {'title': 'User Directory'},
  ('pubsub', 'service'): {'title': 'PubSub', 'description': 'Publish-Subscribe'},
  ('pubsub', 'pep'): {'title': 'PEP', 'description': 'Personal Eventing Protocol'},
#  ('component', 'presence'): {'title': 'Web Presence'},
  ('store', 'file'): {'title': 'File Storage'},
  ('headline', 'newmail'): {'title': 'Mail Alerts'},
#  ('headline', 'rss'): {'title': 'RSS', 'description': 'RSS notifications'},
#  ('headline', 'weather'): {'title': 'Weather'},
  ('proxy', 'bytestreams'): {'title': 'Proxy', 'description': 'File transfer proxy'},
  'uptime': {'title': 'Uptime'},
  'times_online': {'title': '% Uptime'}
}

SERVERS_HOMEPAGE = {
	'jabberd14': 'http://jabberd.org/',
	'jabberd2': 'http://jabberd2.xiaoka.com/',
	'ejabberd': 'http://www.process-one.net/en/ejabberd/',
	'isode m-link': 'http://www.isode.com/evaluate/instant-messaging-xmpp.html',
	'openfire': 'http://www.igniterealtime.org/projects/openfire/index.jsp',
	'prosody': 'http://prosody.im/',
	'tigase': 'http://www.tigase.org/',
	'metronome': 'http://www.lightwitch.org/metronome'
}

# Load the configuration
SCRIPT_DIR = abspath(dirname(sys.argv[0]))
cfg = SafeConfigParser()
cfg.readfp(open(join(SCRIPT_DIR, 'config.cfg')))
OUTPUT_DIRECTORY      = cfg.get("Output configuration", "OUTPUT_DIRECTORY")
SHRINK_SERVERNAMES    = cfg.getboolean("Output configuration", "HTML_SHRINK_SERVERNAMES")
SHRINK_SERVERNAMES_TO = cfg.getint("Output configuration", "HTML_SHRINK_SERVERNAMES_TO")

def _get_filename(directory, filename_prefix, by=None, extension='.html'):
	if by is None:
		return join(directory, filename_prefix+extension)
	elif isinstance(by, tuple) and len(by)==2:
		return join(directory, filename_prefix+'_by_'+by[0]+'_'+by[1]+extension)
	else:
		return join(directory, filename_prefix+'_by_'+by+extension)


def _count_components(server, service_type=None, availability='both'):
	"""Count server components.
	If the same component provides two or more services, it's counted both times
	Components can be restricted to be from service_type type only.
	Components can be restricted using their availability.
	Availability values: ('available', 'unavailable', 'both')."""
	
	if service_type is None:
		num = 0
		
		if availability == 'available' or availability == 'both':
			for service_type in server['available_services']:
				num += len(server['available_services'][service_type])
		if availability == 'unavailable' or availability == 'both':
			for service_type in server['unavailable_services']:
				num += len(server['unavailable_services'][service_type])
		return num
	else:
		if availability == 'available':
			if service_type in server['available_services']:
				return len(server['available_services'][service_type])
			else:
				return 0
		if availability == 'unavailable':
			if service_type in server['unavailable_services']:
				return len(server['unavailable_services'][service_type])
			else:
				return 0
		if availability == 'both':
			num = 0
			if service_type in server['available_services']:
				num += len(server['available_services'][service_type])
			if service_type in server['unavailable_services']:
				num += len(server['unavailable_services'][service_type])
			return num


def _get_table_header(types, sort_by=None, sort_links=None):
	header = "\t<tr class='table_header'>"
	
	text = COLUMNS_DESCRIPTION['server'] if 'server' in COLUMNS_DESCRIPTION else 'Server'
	
	link = "<a href='%s'>%s</a>" % (
	         _get_filename( sort_links['directory'], sort_links['filename_prefix']),
	         text)
	header += ( "<th class='server'>%s</th>" % 
	                 link if sort_links is not None else text )
	
	columns = list(types)
	columns.extend(['uptime', 'times_online'])
	for column_id in columns:
		
		if column_id in COLUMNS_DESCRIPTION:
			text = COLUMNS_DESCRIPTION[column_id]['title']
		else:
			if column_id in types:
				text = column_id[1]
			else:
				text = column_id
		
		link = "<a href='%s'%s>%s</a>" % (
			        _get_filename( sort_links['directory'], sort_links['filename_prefix'], column_id ),
		            " title='%s'" % COLUMNS_DESCRIPTION[column_id]['description'] if 'description' in COLUMNS_DESCRIPTION[column_id] else '',
			        text )
		th_class = "%s_%s" % (column_id[0], column_id[1]) if column_id in types else column_id
		header += "<th class='%s'>%s</th>" % ( th_class, link if sort_links is not None else text )
	
	header += "</tr>\n"
	
	return header

FILES = [basename(f) for f in iglob(join(OUTPUT_DIRECTORY, 'images', '*.png'))]
def _get_image_filename(service_type, available):
	
	if not isinstance(service_type, tuple):
		raise Exception('Wrong service type')
	
	if available:
		filename = "%s_%s.png" % (service_type[0], service_type[1])
	else:
		filename = "%s_%s-grey.png" % (service_type[0], service_type[1])
	
	if filename in FILES:
		return 'images/%s' % filename
	else:
		if available:
			return 'images/yes.png'
		else:
			return 'images/yes-grey.png'

def _get_server_implementation_info(server_version):
	
	if server_version is not None:
		if server_version['name'] == 'jabberd' and server_version['version'].startswith('1.'):
			servername = 'jabberd14'
			serverweb = 'http://jabberd.org/'
		elif server_version['name'] == 'jabberd' and server_version['version'].startswith('2.'):
			servername = 'jabberd2'
		elif server_version['name'] in ('Wildfire', 'Openfire Enterprise'):
			servername = 'openfire'
		else:
			servername = server_version['name'].lower()
		
		serverweb = SERVERS_HOMEPAGE.get(servername, None)
		
		if '%s.png' % servername in FILES:
			image = 'images/%s.png' % servername
		else:
			image = 'images/transparent.png'
		
		return (servername, serverweb, image)
	else:
		return (None, None, 'images/transparent.png')


ROWS = None

def get_rows(servers, types):
	"""Generate the HTML code for the table rows (without the <tr> element!)
	Use singleton to generate them only once"""
	
	global ROWS
	
	if ROWS is not None:
		return ROWS
	
	ROWS = {}
	
	component_jid = lambda component: component.get('jid')
	
	for server_key, server in servers.iteritems():
		
		jid = server['jid']
		
		if SHRINK_SERVERNAMES and len(jid) > SHRINK_SERVERNAMES_TO:
			server_name = (jid[:SHRINK_SERVERNAMES_TO-3] + '...')
		else:
			server_name = jid
		
		tooltip = jid
		
		if 'about' in server and 'homepage' in server['about']:
			server_name = "<a href='%s' name='%s' >%s</a>" % (server['about']['homepage'], jid, server_name)
			tooltip = u"<a href='%s'>%s</a>" % (server['about']['homepage'], tooltip)
		else:
			server_name = "<a name='%s' >%s</a>" % (jid, server_name)
		
		tooltip = u"<strong>%s</strong><ul>" % tooltip
		
		if 'about' in server:
			if 'latitude' in server['about'] and 'longitude' in server['about']:
				if 'city' in server['about'] and 'country' in server['about']:
					tooltip = u"%s<li><a href='http://maps.google.com/maps?q=%s,+%s+(%s)&iwloc=A&hl=en'>Location: %s, %s</a></li>" % (
					          tooltip, server['about']['latitude'], server['about']['longitude'], jid,
					          server['about']['city'], server['about']['country'])
				elif 'country' in server['about']:
					tooltip = u"%s<li><a href='http://maps.google.com/maps?q=%s,+%s+(%s)&iwloc=A&hl=en'>Location: %s</a></li>" % (
					          tooltip, server['about']['latitude'], server['about']['longitude'], jid,
					          server['about']['country'])
				else:
					tooltip = u"%s<li><a href='http://maps.google.com/maps?q=%s,+%s+(%s)&iwloc=A&hl=en'>Location</a></li>" % (
					          tooltip, server['about']['latitude'], server['about']['longitude'], jid)
			elif 'city' in server['about'] and 'country' in server['about']:
				tooltip = u"%s<li><a href='http://maps.google.com/maps?q=%s,+%s+(%s)&iwloc=A&hl=en'>Location: %s, %s</a></li>" % (
				          tooltip, server['about']['city'], server['about']['country'], jid,
				          server['about']['city'], server['about']['country'])
			elif 'country' in server['about']:
				tooltip = u"%s<li>Location: %s</li>" % (tooltip, server['about']['country'])
		
		if 'ipv6_ready' in server and server['ipv6_ready']:
			tooltip = u"%s<li>IPv6 Ready</li>" % tooltip
		
		tooltip = u"%s</ul>" % tooltip
		
		if 'about' in server and 'description' in server['about']:
			assert server['about']['description'] is not None
			tooltip = u"%s<p>%s</p>" % (tooltip, html_escape(server['about']['description']))
			
		
		server_text = u"<div class='tooltip_container'>%s<div class='tooltip'><span>%s</span></div></div>" % (
					server_name, tooltip )
		
		if 'version' in server:
			(impl_name, impl_web, impl_logo) = _get_server_implementation_info(server['version'])
			version_info = u"%s - %s" % (server['version']['name'], server['version']['version'])
		else:
			(impl_name, impl_web, impl_logo) = _get_server_implementation_info(None)
			version_info = ''
		
		impl_text = "<img src='%s' width='16' height='16' alt='%s' title='%s'/>" % (
				impl_logo, version_info, version_info)
		
		if impl_web:
			impl_text = "<a href='%s'>%s</a>" % (impl_web, impl_text)
		
		row = ( u"""<td class='server'>%s %s</td>""" %
		        (impl_text,  server_text) )
		
		for service_type in types:
			
			if (  service_type not in server['available_services'] and 
				  service_type not in server['unavailable_services']  ):
				row += """<td class='feature no %s_%s'></td>""" % (
				                            service_type[0], service_type[1])
			else:
				if service_type in server['available_services']:
					service_available = True
				else:
					service_available = False
				
				row += """<td class='feature yes %s %s_%s'>""" % (
				           'available' if service_available else 'unavailable',
				           service_type[0], service_type[1] )
				
				row += "<div class='tooltip_container'>"
				row += ("""<img src='%s' width='16' height='16' alt='Yes' />""" %
				           _get_image_filename(service_type, service_available))
				
				row += "<div class='tooltip'>"
				if service_type in server['available_services']:
					for component in sorted( server['available_services'][service_type],
					                         key=component_jid ):
						row += """<span class='available'>%s</span>""" % (
						  "%s (%s)" % (component[u'jid'], component[u'node']) if 'node' in component else component[u'jid'] )
				if service_type in server['unavailable_services']:
					for component in sorted( server['unavailable_services'][service_type],
					        key=component_jid ):
						row += """<span class='unavailable'>%s</span>""" % (
						  "%s (%s)" % (component[u'jid'], component[u'node']) if 'node' in component else component[u'jid'] )
				row += "</div></div></td>"
				
		if server['offline_since'] is None:
			if 'uptime' in server:
				uptime = timedelta(seconds=server['uptime'])
				#uptime_text = "%dd, %dh, %dm, %ds" % (
				               #uptime.days, uptime.seconds / 3600,
				               #uptime.seconds % 3600 / 60, uptime.seconds % 60 )
				uptime_text = str(uptime)
			else:
				uptime_text = ''
		else:
			uptime_text = "Offline since %s" % server['offline_since'].strftime('%d %b %Y %H:%M UTC')
		
		row += "<td class='uptime'>%s</td>" % uptime_text
		
		row += "<td class='times_online'>%d%% (%d/%d)</td>" % (
		        int(100*server['times_queried_online']/server['times_queried']),
		        server['times_queried_online'], server['times_queried'])
		
		ROWS[server_key] = row
	
	return ROWS
	


def generate( filename, servers, types, sort_by=None, sort_links=None,
              minimun_uptime=0, compress=False ):
	"""Generate a html file with the servers information.
	Don't display times_offline, to avoid a database access.
	If sort_links is not None, it will be a dictionary with the following keys:
	'directory' and 'filename_prefix'. They will be used to build the links in the header table."""
	
	if minimun_uptime > 0:
		# Filter by uptime
		_servers = {}
		_servers.update([(k,v) for k,v in servers.iteritems() if float(v['times_queried_online'])/v['times_queried'] > minimun_uptime])
		servers = _servers
	
	
	tmpfilename = "%s.tmp" % filename
	
	logging.info('Writing HTML file  temporary "%s" ordered by %s', tmpfilename, sort_by)
	
	# Get the table rows in HTML (without <tr> element)
	rows = get_rows(servers, types)
	
	
	# Sort servers by columns
	server_keys = servers.keys()
	
	if sort_by is None:
		# Assume that the servers are sorted by name
		sort_by = 'server'
		server_keys.sort()
	elif sort_by is 'server':
		# If it's a explicit request, then sort
		server_keys.sort()
	elif sort_by is 'uptime':
		
		# None is earlier than any date, so use current date
		now = datetime.utcnow()
		offline_since = lambda key: servers[key]['offline_since'] if servers[key]['offline_since'] is not None else now
		uptime = lambda key: servers[key]['uptime'] if 'uptime' in servers[key] else 0
		
		server_keys.sort()
		server_keys.sort(key=uptime, reverse=True)
		server_keys.sort(key=offline_since, reverse=True)
	elif sort_by is 'times_online':
		
		times = lambda key: float(servers[key]['times_queried_online'])/servers[key]['times_queried']
		server_keys.sort()
		server_keys.sort(key=times, reverse=True)
	else:
		# Sort servers
		
		num_available_components = (
		    lambda key: _count_components( servers[key], service_type=sort_by,
		                                   availability='available') )
		num_unavailable_components = (
		    lambda key: _count_components( servers[key], service_type=sort_by,
		                                   availability='unavailable') )
		
		# Stable sort
		server_keys.sort()
		server_keys.sort(key=num_unavailable_components, reverse=True)
		server_keys.sort(key=num_available_components, reverse=True)
	
	
	f = open(tmpfilename, "w+")
	
	f.write(
"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
	<head>
		<meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
		<title>Jabber/XMPP Server List</title>
		<style type="text/css">
			body{
				font-family: verdana, tahoma, sans-serif;
				font-size: 0.8em;
				background: #FFF;
				}
			div#header{
				padding: 5px;
				margin:2px auto;
				}
			h1, h2, h3, h4, h5{
				text-shadow: 0.1em 0.1em #AAA;
				font-weight: bold;
			}
			h1{
				font-size: 3em;
			}
			h2{
				font-size: 2.5em;
			}
			h3{
				font-size: 2em;
			}
			h4{
				font-size: 1.6em;
			}
			h5{
				font-size: 1.4em;
			}
			h6{
				font-size: 1.2em;
			}
			a[href]{
				text-decoration: none;
				color: #0000AA;
			}
			a img{
				border: 0px;
			}
			.note{
				padding: 5px;
				margin:2px auto;
				background: #FFC;
				}
			.footer{
				color: gray;
				font-size: 0.8em;
				text-align: center;
				margin: 5px;
				}
			table{
				border-collapse: collapse;
				border-spacing: 0px;
				/*background: #C4DCFF;*/
				background: #EEE;
				width: 100%;
				font-size: 0.85em;
				}
			td, th{
				vertical-align: middle;
				text-align: center;
				padding: 2px 2px;
				}
			tr.table_header{
				background: #DFDFDF;
				}
			tr.table_header th:hover{
				background: #EFEFEF;
				}
			tr.table_header th a{
				text-decoration: none;
				font-weight: normal;
				color: #0000AA;
				}
			tr.table_header th a:hover{
				text-decoration: underline;
				}
			tr.odd{
				background:#EBF4FF;
				}
			tr.even{
				background:#FFF;
				}
			tr.offline{
				font-style: italic;
				background:#FFD4D4;
				}
			th.server, td.server{
				text-align: left;
				padding: 2px;
				}
			th.times_offline,td.times_offline{
				/*display: none;*/
			}
			td.feature{
/* 				font-size: 2em; */
			}
			.no{
				color: #E90900;/*firebrick;*/
			}
			.yes, .available{
				color: #0A0;/*green;*/
			}
			.unavailable{
				color: #808080;/*gray;*/
			}
"""
	)
	
	# Apply a different style to sorted columns
	sort_class = sort_by if not isinstance(sort_by, tuple) else "%s_%s" % sort_by
	f.write(
"""
			tr.table_header th.%s{
				background: #CFCFCF;
				}
			tr.table_header th.%s a{
				font-weight: bolder;
				font-size: 1em;
/* 				background: #FAFAFA; */
				color: #0000FF;
				}
			tr.odd td.%s{
				background: #DCE5EF;
			}
			tr.even td.%s{
				background: #EFEFEF;
			}
			tr.offline td.%s{
				font-style: italic;
				background:#FFD4D4;
				}""" % (sort_class, sort_class, sort_class, sort_class, sort_class)
	)
	
	f.write(
"""
			div.tooltip span{
				display: block;
				/*font-size: 0.7em;*/
				white-space: nowrap;
			}
			/*td div.tooltip{
				display: none;
			}
			td:hover div.tooltip{
				display: block;
			}*/
			div.tooltip_container{
				position: relative;
				display: inline;
			}
			div.tooltip{
				display: none;
				background: #FFC;
				z-index: 1;
			}
			th:hover div.tooltip, td:hover div.tooltip{
				display: block;
				margin: 0px auto;
				position: absolute;
				top: 15px;
				left: 15px;
				padding: 3px;
			}
			td.server div.tooltip{
				padding: 5px 10px;
				width: 200px;
				text-align: center;
			}
			td.server div.tooltip span{
				white-space: normal;
			}
			td.server div.tooltip ul{
				list-style-type: none;
				margin-left: 0px;
				padding-left: 0px;
			}
			td.server div.tooltip p{
				text-align: left;
			}
		</style>
	</head>
	<body>
		<div id='header'>
			<div id='title'><h2>Jabber/<abbr title="eXtensible Messaging and Presence Protocol">XMPP</abbr> Server List</h2></div>
			<h4>Notes:</h4>
			<div class='note'>If the service Jabber ID is from a different domain than the server, it will be ignored.</div>
			<div class='note'>Greyed icons mean that those services aren't accesible from external servers or that those gateways can't be used by users from another servers.</div>
		</div>
		<table>
"""
	)
	
	cols = "\t\t\t<col class='server' />"
	for service_type in types:
		cols += "<col class='%s_%s' />" % (service_type[0], service_type[1])
	cols += "<col class='uptime' /><col class='times_online' />\n"
	
	f.write(cols)
	
	table_header = _get_table_header(types, sort_by, sort_links)
	row_number = 0
	
	for row_number, server_key in enumerate(server_keys):
		
		if row_number % ROWS_BETWEEN_TITLES == 0:
			f.write(table_header)
		
		offline = servers[server_key]['offline_since'] is not None
		
		f.write( (u"<tr class='%s%s'>%s</tr>\n" %
		                     ( 'offline ' if offline else '',
		                       'odd' if row_number % 2 == 1 else 'even',
		                       rows[server_key] )).encode('utf-8') )
		
	if row_number % ROWS_BETWEEN_TITLES != 1:
		f.write(table_header)
	
	f.write(u"""</table><div class='footer'>Page generated on %s by <a href='https://github.com/Tallefer/xmpp-server-scanner'>XMPP Server Scanner</a><!-- %s --></div></body></html>\n""" %
	                    (datetime.utcnow().strftime('%d-%B-%Y %H:%M UTC'), get_version()) )
	
	
	if compress:
		tmpgzfilename = "%s.gz.tmp" % filename
		logging.info( 'Creating a compressed version of file "%s"', tmpfilename )
		f.seek(0)
		gzf = gzip.open(tmpgzfilename, "wb")
		gzf.writelines(f.readlines())
		gzf.close()
		shutil.move(tmpgzfilename, filename+'.gz')
		
	f.close()
	
	shutil.move(tmpfilename, filename)
	
	if compress:
		logging.info('%s generated and compresed as %s.gz', filename, filename)
	else:
		logging.info('%s generated', filename)


def generate_all( directory, filename_prefix, servers, types, minimun_uptime=0,
                  compress=False ):
	'''Generate a set of HTML files sorted by different columns'''
	
	extension = '.html'
	
	sort_links = { 'directory': '.', 'filename_prefix': filename_prefix }
	
	# Name
	generate( _get_filename( directory, filename_prefix, extension=extension ),
	          servers, types, sort_links=sort_links, minimun_uptime=minimun_uptime,
              compress=compress )
	
	for service_type in types:
		generate( _get_filename( directory, filename_prefix, by=service_type,
		                         extension=extension ),
		          servers, types, sort_by=service_type, sort_links=sort_links,
		          minimun_uptime=minimun_uptime, compress=compress )
	
	generate( _get_filename( directory, filename_prefix, by='uptime',
	                         extension=extension ),
	          servers, types, sort_by='uptime', sort_links=sort_links,
	          minimun_uptime=minimun_uptime, compress=compress )
	generate( _get_filename( directory, filename_prefix, by='times_online',
	                         extension=extension ),
	          servers, types, sort_by='times_online', sort_links=sort_links,
	          minimun_uptime=minimun_uptime, compress=compress )
