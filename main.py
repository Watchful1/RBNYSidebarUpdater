#!/usr/bin/python3

import praw
import os
import logging.handlers
from lxml import html
import requests
import datetime
import time
import sys
import traceback
import json
import configparser
import re

### Config ###
LOG_FOLDER_NAME = "logs"
SUBREDDIT = "rbny"
SUBREDDIT_TEAMS = "mls"
USER_AGENT = "RBNYSideBarUpdater (by /u/Watchful1)"
TEAM_NAME = "New York Red Bulls"

### Logging setup ###
LOG_LEVEL = logging.DEBUG
if not os.path.exists(LOG_FOLDER_NAME):
    os.makedirs(LOG_FOLDER_NAME)
LOG_FILENAME = LOG_FOLDER_NAME+"/"+"bot.log"
LOG_FILE_BACKUPCOUNT = 5
LOG_FILE_MAXSIZE = 1024 * 256

log = logging.getLogger("bot")
log.setLevel(LOG_LEVEL)
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
log_stderrHandler = logging.StreamHandler()
log_stderrHandler.setFormatter(log_formatter)
log.addHandler(log_stderrHandler)
if LOG_FILENAME is not None:
	log_fileHandler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=LOG_FILE_MAXSIZE, backupCount=LOG_FILE_BACKUPCOUNT)
	log_formatter_file = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
	log_fileHandler.setFormatter(log_formatter_file)
	log.addHandler(log_fileHandler)

comps = [{'name': 'MLS', 'link': '/MLS', 'acronym': 'MLS'}
	,{'name': 'Preseason', 'link': '/MLS', 'acronym': 'UNK'}
	,{'name': 'CONCACAF', 'link': 'http://category/champions-league/schedule-results', 'acronym': 'CCL'}
	,{'name': 'Open Cup', 'link': '/MLS', 'acronym': 'OPC'}
]


def getCompLink(compName):
	for comp in comps:
		if comp['name'] in compName:
			return comp['link']

	return ""


def matchesTable(table, str):
	for item in table:
		if str in item:
			return True
	return False


teams = []


def getTeamLink(name, useFullname=False, nameOnly=False):
	for item in teams:
		if item['contains'].lower() in name.lower():
			if nameOnly:
				return (item['contains'] if useFullname else item['acronym'])
			else:
				return ("["+(item['contains'] if useFullname else item['acronym'])+"]("+item['link']+")", item['include'])

	if nameOnly:
		return ""
	else:
		return ("", False)


channels = [{'contains': 'ESPN2', 'link': 'http://espn.go.com/watchespn/index/_/sport/soccer-futbol/channel/espn2', 'exact': True, 'allowMLS': False}
    ,{'contains': 'ESPN', 'link': 'http://www.espn.com/watchespn/index/_/sport/soccer-futbol/channel/espn', 'exact': True, 'allowMLS': False}
	,{'contains': 'FS1', 'link': 'http://msn.foxsports.com/foxsports1', 'exact': False, 'allowMLS': False}
	,{'contains': 'FS2', 'link': 'https://en.wikipedia.org/wiki/Fox_Sports_2', 'exact': False, 'allowMLS': False}
	,{'contains': 'UDN', 'link': 'http://www.univision.com/deportes/futbol/mls', 'exact': False, 'allowMLS': False}
	,{'contains': 'Univision', 'link': 'http://www.univision.com/deportes/futbol/mls', 'exact': True, 'allowMLS': False}
	,{'contains': 'UniMás', 'link': 'http://tv.univision.com/unimas', 'exact': False, 'allowMLS': False}
	,{'contains': 'facebook.com', 'link': 'http://www.live.fb.com/', 'exact': False, 'allowMLS': True}
	,{'contains': 'FOX', 'link': 'http://www.fox.com/', 'exact': True, 'allowMLS': False}
	,{'contains': 'beIN', 'link': 'http://www.beinsport.tv/', 'exact': False, 'allowMLS': True}
	,{'contains': 'TSN', 'link': '#tsn', 'exact': False, 'allowMLS': True}
	,{'contains': 'MLS LIVE', 'link': 'http://live.mlssoccer.com/mlsmdl', 'exact': False, 'allowMLS': True}
]
msgLink = 'http://www.msgnetworks.com/teams/red-bulls/'


def getChannelLink(name, replaceMLSLive=False):
	stations = name.split(',')
	strList = []
	included = set()
	allowMLS = True
	for item in channels:
		for station in stations:
			if item['contains'] not in included:
				if len(strList) < 3 or (len(strList) < 6 and (item['contains'] != "MLS LIVE" or allowMLS)):
					if (item['exact'] and item['contains'] == station.strip()) or (not item['exact'] and item['contains'] in station):
						included.add(item['contains'])
						strList.append("[](")
						strList.append(msgLink if replaceMLSLive and item['contains'] == "MLS LIVE" else item['link'])
						strList.append(")")
						if not item['allowMLS']:
							allowMLS = False

	return ''.join(strList)


### Parse table ###
def compareTeams(team1, team2):
	if int(team1['points']) > int(team2['points']):
		return True
	elif int(team1['points']) < int(team2['points']):
		return False
	else:
		if int(team1['wins']) > int(team2['wins']):
			return True
		elif int(team1['wins']) < int(team2['wins']):
			return False
		else:
			if int(team1['goalDiff']) > int(team2['goalDiff']):
				return True
			elif int(team1['goalDiff']) < int(team2['goalDiff']):
				return False
			else:
				if int(team1['goalsFor']) > int(team2['goalsFor']):
					return True
				elif int(team1['goalsFor']) < int(team2['goalsFor']):
					return False
				else:
					log.error("Ran out of tiebreakers")
					return True

def parseTable():
	page = requests.get("http://www.mlssoccer.com/standings")
	tree = html.fromstring(page.content)

	firstConf = {'name': "E", 'size': 11}
	secondConf = {'name': "W", 'size': 11}
	standings = []
	for i in range(0, firstConf['size']+secondConf['size']):
		standings.append({'conf': (firstConf['name'] if i < firstConf['size'] else secondConf['name'])})

	elements = [{'title': 'Points', 'name': 'points'}
		,{'title': 'Games Played', 'name': 'played'}
		,{'title': 'Goals For', 'name': 'goalsFor'}
		,{'title': 'Goal Difference', 'name': 'goalDiff'}
		,{'title': 'Wins', 'name': 'wins'}
	]

	for element in elements:
		for i, item in enumerate(tree.xpath("//td[@data-title='"+element['title']+"']/text()")):
			standings[i][element['name']] = item

	for i, item in enumerate(tree.xpath("//td[@data-title='Club']")):
		names = item.xpath(".//a/text()")
		if not len(names):
			log.warning("Couldn't find team name")
			continue
		teamName = ""
		for name in names:
			if len(name) > len(teamName):
				teamName = name

		standings[i]['name'] = name


	sortedStandings = []
	firstCount = 0
	secondCount = firstConf['size']
	while True:
		if compareTeams(standings[firstCount], standings[secondCount]):
			standings[firstCount]['ranking'] = firstConf['name'] + str(firstCount + 1)
			sortedStandings.append(standings[firstCount])
			firstCount += 1
		else:
			standings[secondCount]['ranking'] = secondConf['name'] + str(secondCount - firstConf['size'] + 1)
			sortedStandings.append(standings[secondCount])
			secondCount += 1

		if firstCount == firstConf['size']:
			while True:
				standings[secondCount]['ranking'] = secondConf['name'] + str(secondCount - firstConf['size'] + 1)
				sortedStandings.append(standings[secondCount])
				secondCount += 1

				if secondCount == firstConf['size'] + secondConf['size']:
					break

			break

		if secondCount == firstConf['size'] + secondConf['size']:
			while True:
				standings[firstCount]['ranking'] = firstConf['name'] + str(firstCount + 1)
				sortedStandings.append(standings[firstCount])
				firstCount += 1

				if firstCount == firstConf['size']:
					break

			break

	return sortedStandings


def printTable(standings):
	strList = []
	strList.append("**[Standings](http://www.mlssoccer.com/standings)**\n\n")
	strList.append("*")
	strList.append(datetime.datetime.now().strftime("%m/%d/%y"))
	strList.append("*\n\n")
	strList.append("Pos | Team | Pts | GP | GF | GD\n")
	strList.append(":--:|:--:|:--:|:--:|:--:|:--:\n")

	for team in standings:
		strList.append(team['ranking'])
		strList.append(" | ")
		strList.append(getTeamLink(team['name'])[0])
		strList.append(" | **")
		strList.append(team['points'])
		strList.append("** | ")
		strList.append(team['played'])
		strList.append(" | ")
		strList.append(team['goalsFor'])
		strList.append(" | ")
		strList.append(team['goalDiff'])
		strList.append(" |\n")

	strList.append("\n\n\n")
	return strList


### Parse schedule ###
def parseSchedule():
	page = requests.get("https://www.newyorkredbulls.com/schedule?year=2017")
	tree = html.fromstring(page.content)

	schedule = []
	date = ""
	for i, element in enumerate(tree.xpath("//ul[contains(@class,'schedule_list')]/li[contains(@class,'row')]")):
		match = {}
		dateElement = element.xpath(".//div[contains(@class,'match_date')]/text()")
		if not len(dateElement):
			log.warning("Couldn't find date for match, skipping")
			continue

		timeElement = element.xpath(".//span[contains(@class,'match_time')]/text()")
		if not len(timeElement):
			log.warning("Couldn't find time for match, skipping")
			continue

		if 'TBD' in timeElement[0]:
			match['datetime'] = datetime.datetime.strptime(dateElement[0] + timeElement[0], "%A, %B %d, %Y")
			match['status'] = 'tbd'
		else:
			match['datetime'] = datetime.datetime.strptime(dateElement[0], "%A, %B %d, %Y %I:%M%p ET")
			match['status'] = ''

		statusElement = element.xpath(".//span[contains(@class,'match_result')]/text()")
		if len(statusElement):
			match['status'] = 'final'
			homeScores = re.findall('(\d+).*-', statusElement[0])
			if len(homeScores):
				match['homeScore'] = homeScores[0]
			else:
				match['homeScore'] = -1

			awayScores = re.findall('-.*(\d+)', statusElement[0])
			if len(awayScores):
				match['awayScore'] = awayScores[0]
			else:
				match['awayScore'] = -1
		else:
			match['status'] = ''
			match['homeScore'] = -1
			match['awayScore'] = -1

		opponentElement = element.xpath(".//div[contains(@class,'match_matchup')]/text()")
		homeAwayElement = element.xpath(".//span[contains(@class,'match_home_away')]/text()")

		if not len(opponentElement) or not len(homeAwayElement):
			log.debug("Could not find any opponent")
			continue

		if homeAwayElement[0] == 'H':
			match['home'] = TEAM_NAME
			match['away'] = opponentElement[0]
		elif homeAwayElement[0] == 'A':
			match['home'] = opponentElement[0][3:]
			match['away'] = TEAM_NAME
		else:
			log.debug("Could not find opponent")
			continue

		compElement = element.xpath(".//span[contains(@class,'match_competition ')]/text()")
		if len(compElement):
			match['comp'] = compElement[0]
		else:
			match['comp'] = ""

		tvElement = element.xpath(".//div[contains(@class,'match_info')]/text()")
		if len(tvElement):
			match['tv'] = tvElement[0]
		else:
			match['tv'] = ""

		schedule.append(match)

	return schedule


log.debug("Connecting to reddit")

once = False
debug = False
user = None
if len(sys.argv) >= 2:
	user = sys.argv[1]
	for arg in sys.argv:
		if arg == 'once':
			once = True
		elif arg == 'debug':
			debug = True
else:
	log.error("No user specified, aborting")
	sys.exit(0)


try:
	r = praw.Reddit(
		user
		,user_agent=USER_AGENT)
except configparser.NoSectionError:
	log.error("User "+user+" not in praw.ini, aborting")
	sys.exit(0)

while True:
	startTime = time.perf_counter()
	log.debug("Starting run")

	strList = []
	skip = False

	schedule = []
	standings = []
	try:
		resp = requests.get(url="https://www.reddit.com/r/"+SUBREDDIT_TEAMS+"/wiki/sidebar-teams.json", headers={'User-Agent': USER_AGENT})
		jsonData = json.loads(resp.text)
		teamText = jsonData['data']['content_md']

		firstLine = True
		for teamLine in teamText.splitlines():
			if firstLine:
				firstLine = False
				continue
			if teamLine.strip() == "":
				continue
			teamArray = teamLine.strip().split('|')
			if len(teamArray) < 4:
				log.warning("Couldn't parse team line: " + teamLine)
				continue
			team = {'contains': teamArray[0]
				,'acronym': teamArray[1]
				,'link': teamArray[2]
				,'include': True if teamArray[3] == 'include' else False
			}
			teams.append(team)

		schedule = parseSchedule()
		standings = parseTable()
	except Exception as err:
		log.warning("Exception parsing schedule")
		log.warning(traceback.format_exc())
		skip = True

	try:
		teamGames = []
		nextGameIndex = -1
		for game in schedule:
			if game['home'] == TEAM_NAME or game['away'] == TEAM_NAME:
				teamGames.append(game)
				if game['datetime'] + datetime.timedelta(hours=2) > datetime.datetime.now() and nextGameIndex == -1:
					nextGameIndex = len(teamGames) - 1

		strList.append("##Upcoming Events\n\n")
		strList.append("Description|Time (ET)|TV\n")
		strList.append("---|---:|:---:|---|\n")
		for game in teamGames[nextGameIndex:nextGameIndex+4]:
			strList.append("**")
			strList.append(game['datetime'].strftime("%m/%d"))
			strList.append("**[](")
			strList.append(getCompLink(game['comp']))
			strList.append(")||")
			if game['home'] == TEAM_NAME:
				strList.append("**Home**|\n")
				homeLink, homeInclude = getTeamLink(game['away'], True)
				strList.append(homeLink)
			else:
				strList.append("*Away*|\n")
				awayLink, awayInclude = getTeamLink(game['home'], True)
				strList.append(awayLink)
			strList.append("|")
			if game['status'] == 'tbd':
				strList.append("TBD")
			else:
				strList.append(game['datetime'].strftime("%I:%M"))
			strList.append("|")
			strList.append(getChannelLink(game['tv'], True))
			strList.append("|\n")

		strList.append("\n\n")
		strList.append("##Previous Results\n\n")
		strList.append("Date|Home|Result|Away\n")
		strList.append(":---:|:---:|:---:|:---:|\n")

		for game in reversed(teamGames[nextGameIndex-4:nextGameIndex]):
			strList.append("[")
			strList.append(game['datetime'].strftime("%m/%d"))
			strList.append("](")
			strList.append(getCompLink(game['comp']))
			strList.append(")|")
			if game['home'] == TEAM_NAME:
				RBNYHome = True
			else:
				RBNYHome = False
			if RBNYHome:
				strList.append("**")
			strList.append(getTeamLink(game['home'], True, True))
			if RBNYHome:
				strList.append("**")
			strList.append("|")
			strList.append(game['homeScore'])
			strList.append("-")
			strList.append(game['awayScore'])
			strList.append("|")
			if not RBNYHome:
				strList.append("**")
			strList.append(getTeamLink(game['away'], True, True))
			if not RBNYHome:
				strList.append("**")
			strList.append("\n")

		strList.append("\n\n")
		strList.append("## MLS Standings\n\n")


	except Exception as err:
		log.warning("Exception parsing table")
		log.warning(traceback.format_exc())
		skip = True

	try:
		strList.extend(printTable(standings))
	except Exception as err:
		log.warning("Exception parsing table")
		log.warning(traceback.format_exc())
		skip = True

	if not skip:
		try:
			subreddit = r.subreddit(SUBREDDIT)
			description = subreddit.description
			begin = description[0:description.find("##Upcoming Events")]
			end = description[description.find("##NYRB II (USL)"):]

			if debug:
				log.info(begin + ''.join(strList) + end)
			else:
				try:
					subreddit.mod.update(description=begin + ''.join(strList) + end)
				except Exception as err:
					log.warning("Exception updating sidebar")
					log.warning(traceback.format_exc())
		except Exception as err:
			log.warning("Broken sidebar")
			log.warning(traceback.format_exc())
			skip = True

	log.debug("Run complete after: %d", int(time.perf_counter() - startTime))
	if once:
		break
	time.sleep(15 * 60)
