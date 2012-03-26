#!/usr/bin/env python

#
# follow.py
#
# Copyright (C) Ross Glass 2012 <fade@entropism.org>
# 
# follow.py is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# main.py is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Prerequisites: One or more XBMC 11.0 (Eden) or higher installation running on a MySQL Database; python MySQLdb component installed
# Optional: Foobar2000 with the foo_httpcontrol component <http://code.google.com/p/foo-httpcontrol/>
# Installation: 
# Copy the directory 'follow_json' to '%appdata%Roaming\foobar2000\foo_httpcontrol_data'
# Create one or more configuration files in the following format:
#
# [database]
# xbmc_db_host: localhost
# xbmc_db_user: xbmc
# xbmc_db_passwd: xbmc
# xbmc_db_db: xbmc_music18
#
# [from]
# host: htpc
# xbmc_port: 80
# fb2k_port: 8888
#
# [to]
# host: office
# xbmc_port: 80
# fb2k_port: 8888
#
#
# xbmc_port and fb2k_port are optional, but each host should have at least one or the other. If both xbmc and fb2k ports are defined and 
# running on the target host, fb2k playback will be given precedence for music. Otherwise both music and video will be sent to xbmc
#
# invoke the script by passing in the path to a config file, and optionaly the 'debug' option to return each http call made
# ex: follow.py ./htpc_office debug

import json
import urllib2
import sys
import os
import time
import ConfigParser
import socket
import MySQLdb

def get_sockets(host, port):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.settimeout(.5)
	isUp = 0
	try:
		result=s.connect_ex((host, int(port)))
		if(result == 0):
			isUp = 1
	except: 
		isUp = 0
	s.close()
	return isUp
	
def get_players(from_xbmc_url, from_fb2k_url):
	
	global from_fb2k_up
	global from_xbmc_up
	
	type = 'none'
	
	if from_fb2k_up == 1:
		type = get_players_fb2k(from_fb2k_url)
			
	if type == 'none' and from_xbmc_up == 1:
		type = get_players_xbmc(from_xbmc_url)
		
	print 'player type: ' + type
	return type
	
def get_players_fb2k(url_fb2k):
	data = '?param3=src/status.json'
	url = url_fb2k

	try:
		f = urllib2.urlopen(url + data)
		response = f.read()
		f.close()
		if debug == 1:
			print 'get fb2k status: ' + url + data	
		
		payload = json.loads(response)
		isPlaying = payload['isPlaying']
		isPaused = payload['isPaused']
		
		if (isPlaying == '1'):
			type = 'fb2k'
		else: 
			type = 'none'
	except:
		print 'fb2k is not running'
		type = 'none'
		
	return type
	
def get_players_xbmc(url_xbmc):
	#Get the active players

	method = 'Player.GetActivePlayers'
	params = '{}'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  url_xbmc
	
	try:
		f = urllib2.urlopen(url, data)
		response = f.read()
		f.close()
		if debug == 1:
			print 'get xbmc players: ' + url + data
		payload = json.loads(response)
		result = payload['result']
		
		if len(result) > 0:
			player = result[0]
			type = player['type']

		else:
			type = 'none'
	except:
		print 'xbmc is not running'
		type = 'none'
	
	return type
	
def stop_album_fb2k(from_fb2k_url):
	#Get the current item
	data = '?param3=src/status.json'
	url = from_fb2k_url

	f = urllib2.urlopen(url + data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'get fb2k nowplaying: ' + url + data
	
	payload = json.loads(response)
	currentItem = payload['currentItem']
	artist = currentItem['artist']
	album = currentItem['album']
	title = currentItem['title']
	track = int(currentItem['index']) + 1
	totalTime = float(currentItem['totalTime'])
	currentTime = float(currentItem['currentTime'])
	percentage = currentTime/totalTime*100
	
	print 'Stopping audio:'
	print artist
	print album
	print 'Will resume at track ' + str(track) + ': ' + title + '(' + str(percentage) + '%)'
	
	albumid = get_album_id(album, artist)
	
	playing = dict([('artist', artist), ('album', album), ('track', track), ('title', title), ('percentage', percentage), ('albumid', albumid)])
	
	data = '?cmd=Stop'
	f = urllib2.urlopen(url + data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'stop fb2k nowplaying: ' + url + data
	
	return playing
	
def stop_album_xbmc(from_xbmc_url):
	#Get the current item
	method = 'Player.GetItem'
	params = '{"playerid": 0, "properties": ["title", "artist", "album", "albumid", "track", "file"] }'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  from_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'get xbmc nowplaying: ' + url + data

	payload = json.loads(response)
	result = payload['result']
	items = result['item']

	title = items['title']
	album = items['album']
	track = items['track']
	artist = items['artist']
	songid = items['id']
	albumid = items['albumid']
	file = items['file']
	dir = os.path.dirname(file)

	#Get the current player properties
	method = 'Player.GetProperties'
	params = '{"playerid": 0, "properties": ["percentage"] }'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  from_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'get xbmc nowplaying' + url + data

	payload = json.loads(response)
	result = payload['result']
	percentage = result['percentage']

	print 'Swapping audio:'
	print artist
	print album
	print 'Will resume at track ' + str(track) + ': ' + title + '(' + str(percentage) + '%)'
	
	playing = dict([('artist', artist), ('album', album), ('track', track), ('title', title), ('percentage', percentage), ('albumid', albumid), ('dir', dir)])

	#stop the current player

	method = 'Player.Stop'
	params = '{"playerid": 0}'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  from_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()		
	if debug == 1:
		print 'stop xbmc nowplaying: ' + url + data
	
	return playing
	
def get_album_id(album, artist):
	db=MySQLdb.connect(host=xbmc_db_host, user = xbmc_db_user, passwd=xbmc_db_passwd,db=xbmc_db_db)
	cursor = db.cursor()
	qry = 'SELECT idAlbum FROM albumview  WHERE strAlbum = "' + album + '" AND strArtist = "' + artist + '"'
	cursor.execute(qry)
	print qry
	row = cursor.fetchone()	
	albumid = row[0]
	cursor.close()
	db.close()
	return albumid
	
def start_album_xbmc(playing, to_xbmc_url):	
		
	#start playing what we got

	method = 'Player.Open'
	params = '{"item": {"albumid":' + str(playing['albumid']) + '}}'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  to_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'start xbmc album: ' + url + data

	#jump to the track

	method = 'Player.GoTo'
	params = '{"playerid": 0, "position": ' + str(playing['track'] - 1) + '}'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  to_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'go to xbmc track: ' + url + data
	
	#jump to the resume point

	method = 'Player.Seek'
	params = '{"playerid": 0, "value": ' + str(playing['percentage']) + '}'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  to_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'go to xbmc resume point: ' + url + data

def start_album_fb2k(playing, to_url_fb2k):

	#convert the directory to UNC
	dir = playing['dir']
	dir = dir.replace('/', '\\')
	dir = dir.replace('smb:', '')
	
	#drop the volume to 0
	data = '?cmd=Volume&param1=0'
	url = to_url_fb2k
	f = urllib2.urlopen(url + data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'drop the volume to 0: ' + url + data	

	#clear the current playlist
	data = '?cmd=EmptyPlaylist'
	url = to_url_fb2k
	f = urllib2.urlopen(url + data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'clear fb2k playlist: ' + url + data
	
	#add the entire album to the playlist
	data = '?cmd=CmdLine&param1=/add ' + '"' + dir + '" /immediate'
	url = to_url_fb2k
	f = urllib2.urlopen(url + data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'add fb2k album: ' + url + data
	
	time.sleep(1)
	
	#jump to the track
	data = '?cmd=Start&param1=' + str(playing['track'] - 1)
	url = to_url_fb2k
	f = urllib2.urlopen(url + data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'start fb2k at track: ' + url + data
	
	time.sleep(1)
	
	#seek to 0
	data = '?cmd=Seek&param1=0'
	url = to_url_fb2k
	f = urllib2.urlopen(url + data)
	response = f.read()
	f.close()	
	if debug == 1:
		print 'seek fb2k to resume point: ' + url + data
		
	#seek to the percentage
	data = '?cmd=Seek&param1=' + str(playing['percentage'])
	url = to_url_fb2k
	f = urllib2.urlopen(url + data)
	response = f.read()
	f.close()	
	if debug == 1:
		print 'seek fb2k to resume point: ' + url + data		
		
	#set the volume to 100
	data = '?cmd=Volume&param1=100'
	url = to_url_fb2k
	f = urllib2.urlopen(url + data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'set the volume to 100: ' + url + data			

def stop_video_xbmc(from_xbmc_url):

#Get the current item
	method = 'Player.GetItem'
	params = '{"playerid": 1, "properties": ["title", "showtitle", "season", "episode", "file"] }'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  from_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'get xbmc nowplaying: ' + url + data

	payload = json.loads(response)
	result = payload['result']
	items = result['item']

	
	title = items['title']
	showtitle = items['showtitle']
	season = items['season']
	episode = items['episode']
	file = items['file']

	
	#Get the current player properties
	method = 'Player.GetProperties'
	params = '{"playerid": 1, "properties": ["percentage"] }'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  from_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'get xbmc percentage: ' + url + data
	payload = json.loads(response)
	result = payload['result']
	percentage = result['percentage']

	
	print 'Swapping Video:'
	if showtitle != '':
		print showtitle
		print 'Season ' + str(season)
		print 'Episode ' + str(episode)
	print title
	print 'Will resume at ' + str(percentage) + '%'

	playing = dict([('showtitle', showtitle), ('season', season), ('episode', episode), ('title', title), ('percentage', percentage),('file', file)])	

	
	#stop the current player

	method = 'Player.Stop'
	params = '{"playerid": 1}'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  from_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()	
	if debug == 1:
		print 'stop xbmc nowplaying: ' + url + data		

	return playing

def start_video_xbmc(playing, to_xbmc_url):
	
	#start playing what we got

	method = 'Player.Open'
	params = '{"item": {"file":"' + playing['file'] + '"}}'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  to_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()
	if debug == 1:
		print 'start xbmc video file: ' + url + data		
		
	#jump to the resume point

	method = 'Player.Seek'
	params = '{"playerid": 1, "value": ' + str(playing['percentage']) + '}'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  to_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()	
	if debug == 1:
		print 'seek xbmc percentage: ' + url + data			
	
def swap_video_xbmc(from_xbmc_url, to_xbmc_url):
	#Get the current item
	method = 'Player.GetItem'
	params = '{"playerid": 1, "properties": ["title", "showtitle", "season", "episode", "file"] }'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  from_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()

	payload = json.loads(response)
	result = payload['result']
	items = result['item']

	
	title = items['title']
	showtitle = items['showtitle']
	season = items['season']
	episode = items['episode']
	file = items['file']

	
	#Get the current player properties
	method = 'Player.GetProperties'
	params = '{"playerid": 1, "properties": ["percentage"] }'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  from_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()

	payload = json.loads(response)
	result = payload['result']
	percentage = result['percentage']

	
	print 'Swapping Video:'
	if showtitle != '':
		print showtitle
		print 'Season ' + str(season)
		print 'Episode ' + str(episode)
	print title
	print 'Will resume at ' + str(percentage) + '%'
	
	#stop the current player

	method = 'Player.Stop'
	params = '{"playerid": 1}'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  from_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()
	
	#start playing what we got

	method = 'Player.Open'
	params = '{"item": {"file":"' + file + '"}}'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  to_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()

	#jump to the resume point

	method = 'Player.Seek'
	params = '{"playerid": 1, "value": ' + str(percentage) + '}'
	data =  '{"jsonrpc": "2.0", "id": 1,  "method": "' + method + '", "params": ' + params + ' }'
	url =  to_xbmc_url
	f = urllib2.urlopen(url, data)
	response = f.read()
	f.close()

	
#check if we're in debug mode or not	
try:
	if sys.argv[2] == 'debug':
		debug = 1
except:
	debug = 0

#get the config values	
config_file = sys.argv[1]
config = ConfigParser.RawConfigParser()
config.read(config_file)

xbmc_db_host = config.get('database', 'xbmc_db_host')
xbmc_db_user = config.get('database', 'xbmc_db_user')
xbmc_db_passwd = config.get('database', 'xbmc_db_passwd')
xbmc_db_db = config.get('database', 'xbmc_db_db')

from_host = config.get('from', 'host')
try:
	from_xbmc_port = config.get('from', 'xbmc_port')
except:
	from_xbmc_port = ''
	
try:
	from_fb2k_port = config.get('from', 'fb2k_port')
except:
	from_fb2k_port = ''
	
to_host = config.get('to', 'host')
try:
	to_xbmc_port = config.get('to', 'xbmc_port')
except:
	to_xbmc_port = ''
try:	
	to_fb2k_port = config.get('to', 'fb2k_port')
except:
	to_fb2k_port = ''
	
#construct the urls to call
from_xbmc_url =  'http://' + from_host + ':' + from_xbmc_port +'/jsonrpc'
to_xbmc_url = 'http://' + to_host + ':' + to_xbmc_port + '/jsonrpc'
from_fb2k_url =  'http://' + from_host + ':' + from_fb2k_port +'/follow_json'
to_fb2k_url = 'http://' + to_host + ':' + to_fb2k_port + '/follow_json'
	
#see what's up
from_fb2k_up = get_sockets(from_host, from_fb2k_port)
from_xbmc_up = get_sockets(from_host, from_xbmc_port)	
to_fb2k_up = get_sockets(to_host, to_fb2k_port)
to_xbmc_up = get_sockets(to_host, to_xbmc_port)	

type = get_players(from_xbmc_url, from_fb2k_url)

if type == 'audio':
	if to_fb2k_up == 1:		
		playing = stop_album_xbmc(from_xbmc_url)
		if debug == 1:
			print 'resuming entity: ' + str(playing)
		start_album_fb2k(playing, to_fb2k_url)
	elif to_xbmc_up == 1:
		playing = stop_album_xbmc(from_xbmc_url)
		if debug == 1:
			print 'resuming entity: ' + str(playing)	
		start_album_xbmc(playing, to_xbmc_url)
	else:
		print 'no available players'

if type == 'fb2k':
	if to_fb2k_up == 1:		
		playing = stop_album_fb2k (from_fb2k_url)
		if debug == 1:
			print 'resuming entity: ' + str(playing)
		start_album_fb2k(playing, to_fb2k_url)
	elif to_xbmc_up == 1:
		playing = stop_album_fb2k (from_fb2k_url)	
		if debug == 1:
			print 'resuming entity: ' + str(playing)	
		start_album_xbmc(playing, to_xbmc_url)
	else:
		print 'no available players'
		
if type == 'video':
	if to_xbmc_up == 1:
		playing = stop_video_xbmc(from_xbmc_url)
		if debug == 1:
			print 'resuming entity: ' + str(playing)	
		start_video_xbmc(playing, to_xbmc_url)	
	else:
		print 'no available players'

	