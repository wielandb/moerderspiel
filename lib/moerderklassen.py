# -*- coding: utf-8 -*-

import wordconstruct
import os, sys
import shutil
import random
import codecs
import utils as utils
from twitmord import twitkill
from datetime import datetime, timedelta
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from collections import defaultdict

def flatten(lst):
	"""Flatten a List of Lists (of Lists...) structure. 
	Returns a list of all elements, regardless of the element depth
	in the List structure.
	"""
	for elem in lst:
		if type(elem) in (tuple, list):
			for i in flatten(elem):
				yield i
		else:
			yield elem
			
def force_datetime(dt):
	formats = [ '%d.%m.%Y %H:%M' ]
	if isinstance(dt, datetime):
		return dt
	if isinstance(dt, int):
		return datetime.utcfromtimestamp(dt)
	if isinstance(dt, basestring):
		dt = dt.strip()
		for f in formats:
			try:
				return datetime.strptime(dt, f)
			except:
				pass
		else:
			try:
				r = parse(dt, fuzzy=True, default=(datetime.now() - relativedelta(minutes=15)) )
				while r > datetime.now():
					r = r - relativedelta(days=1)
				return r
			except:
				pass
	return datetime.now() - relativedelta(minutes=15)
			
class GameMessage(RuntimeError):
	"""This Exception denotes a message to be delivered to the User."""
	def __init__(self, value):
		self.value = value
	def __str__(self):
		if isinstance(self.value, basestring):
			return self.value
		else:
			return repr(self.value)

class GameError(GameMessage):
	"""This Exception denotes an error message to be delivered to the User."""
	def __init__(self, value):
		self.value = value
	def __str__(self):
		if isinstance(self.value, basestring):
			return self.value
		else:
			return repr(self.value)

class Kill:
	"""This data class contains all meta data of a kill.
	
	Attributes:
		* ``killer``: a Participant (regular kill) or None (game master kill)
		* ``date``: a datetime object denoting the time of the kill
		* ``reason``: text describing the kill
	"""
	def __init__(self, killer, date, reason):
		self.killer = killer
		self.date = force_datetime(date)
		self.reason = reason
	def __setstate__(self, state):
		"""Upgrade old pickles."""
		if not isinstance(state['date'], datetime):
			state['date'] = force_datetime(state['date'])
		
		self.__dict__.update(state)

class Player:
	"""This data class contains all meta data of a player.
	
	Attributes:
		* ``name``: name of player (unicode str)
		* ``info``: additional information identifying the player (unicode str).
			This attribute is used to avoid name clashes.
		* ``id``: ID/Code of the player. Reserved for player authentication.
			If the UI supports input/actions by the player that don't relate
			to a kill assignment, the player needs this code to authenticate
			himself.
		* ``public_id``: ID of the player that may be used to identify the
			player in the UI. The player himself does not need to know this ID.
			The UI programmer needs to use this attribute for option lists etc.
	"""
	###TODO: better attribute naming!
	###TODO: refactor all "id" variable names to "signaturecode"???
	def __init__(self, name, info, game, email=''):
		"""Sets name and info text of the Player. Generates id and public_id.
		"""
		self.name = name
		self.info = info
		self.game = game
		self.email = email
		self.id = wordconstruct.WordGenerator().generate(7)
		self.public_id = wordconstruct.WordGenerator().generate(8)
		
	def __str__(self):
		if self.info and len(self.info) > 0:
			return "%s (%s)" % (self.name, self.info)
		else:
			return self.name
			
	def html(self):
		ret = ""
		if self.info and len(self.info) > 0:
			ret = "%s (%s)" % (self.name, self.info)
		else:
			ret = self.name
		return utils.htmlescape(ret)
		
	def sendemail(self, templatefilename='auftraege.txt', subject='Auftraege im Spiel "%s"', attachauftrag=None):
		if self.email is None or len(self.email) < 5:
			return
		if attachauftrag is None:
			# TODO: Check whether 'OPEN' is necessary here. Including it for now in case the game is not 'RUNNING' when the first notifications are sent.
			attachauftrag = (self.game.status in ('RUNNING', 'OPEN'))
		pdfpath = None
		if attachauftrag:
			pdfpath = self.game.pdfgen(players = [self])
		utils.sendemail(
			self.game.templatedir,
			templatefilename, 
			subject % self.game.id,
			'hades@moerderspiel.org',
			self.email,
			self.game,
			self,
			pdfpath
		)
		
	def killcount(self):
		return self.game.getKillsCount(self)
	
	def deathscount(self):
		return self.game.getDeathsCount(self)
		
	def score(self):
		return len([ r for r in self.game.rounds.values() if r.hasParticipant(self) ]) - self.deathscount() + self.killcount()
	
	def pdfgen(self):
		return self.game.pdfgen(players = [self])
	
class Participant:
	"""A participant in a round, roughly equal to a single kill assignment.
	One Player impersonates as many participants as there are rounds in the 
	game. Each Participant links to exactly one Player.
	
	Attributes:
		* ``player``: The corresponding Player object.
		* ``id``: The ID/Code of the kill assignment. Needed to log a kill 
			by a player.
		* ``round``: The Round object this Participant is playing in.
		* ``killedby``: A Kill object if the Participant has been killed.
			Is None if the Participant is still alive.
	"""
	def __init__(self, player, round):
		self.player = player
		self.id = wordconstruct.WordGenerator().generate(7)
		self.round = round
		self.killedby = None
	def __str__(self):
		return u'Spieler %s in Runde %s' % (self.player, self.round)
	
	def alive(self):
		"""Returns True if the Participant is still alive."""
		return (self.killedby is None)
		
	def killed(self):
		"""Returns True if the Participant is killed already."""
		return not self.alive()
	
	def kill(self, killer, date, reason):
		"""Kills the Participant.
		
		Raises GameError if victim is already dead.
		"""
		if self.alive():
			self.killedby = Kill(killer, date, reason)
		else:
			raise GameError(u'%s lebt nicht mehr in dieser Runde' % self.player.name)
	
	def getInitialVictim(self):
		"""Returns the victim of the Participant as another Participant object.
		"""
		return self.round.getInitialVictim(self)

	def getInitialKiller(self):
		"""Returns the killer of the Participant as another Participant object.
		"""
		return self.round.getInitialKiller(self)
	
	def getCurrentVictim(self):
		return self.round.getCurrentVictim(self)
	
	def getCurrentKiller(self):
		return self.round.getCurrentKiller(self)
	
	def canRevert(self):
		if self.killedby:
			return self.round.canRevert(self)
		else:
			return False

class Round:
	"""A single round in the game. A game contains multiple Rounds if the
	players have more than one life (and therefore multiple kill assignments).
	
	Attributes:
		* ``name``: Name of the Round.
		* ``participants``: List of Participants in this Round. May be empty
			if the Game hasn't been started.
	"""
	def __init__(self, name):
		self.name = name
		self.participants = []
	def __str__(self):
		return u'Kreis %s' % self.name
	
	def getParticipant(self, participant_or_player_or_id):
		"""Returns a Participant of this Round, using any of the following
		argument types to find the corresponding Participant object:
			* a Participant,
			* a Player,
			* a Participant's ID/Code as string
			* a Player's ID/Code as string
			* a Player's public_id as string
			
		Returns None if the Participant is not present in this Round.
		"""
		id = ''
		if isinstance(participant_or_player_or_id, Participant) or \
			isinstance(participant_or_player_or_id, Player):
			id = participant_or_player_or_id.id;
		elif isinstance(participant_or_player_or_id, basestring):
			id = participant_or_player_or_id;
		for participant in self.participants:
			if participant.id == id or \
				participant.player.id == id or \
				participant.player.public_id == id:
				return participant
		return None
	
	def hasParticipant(self, participant_or_player_or_id):
		return (self.getParticipant(participant_or_player_or_id) is not None)
	
	def kill(self, killer_public_id, victim_id, date, reason):
		"""Kills a player of this Round. The killer_public_id may be None to
		denote a Game Master kill.
		
		Raises GameError if the victim does not exist in this Round or if the
		victim is not alive anymore.
		"""
		killer = self.getParticipant(killer_public_id)
		victim = self.getParticipant(victim_id)
		#for v in self.participants:
		#	if v.id == victim_id:
		#		victim = v
		if victim is None:
			raise GameError(u'Signaturcode ungültig')
		elif not victim.alive():
			raise GameError(u'%s lebt nicht mehr' % victim.player.name)
		#for k in self.participants:
		#	if k.player.public_id == killer_public_id:
		#		killer = k
		if self.canKill(killer, victim):
			victim.kill(killer, date, reason)
		elif killer_public_id is None:
			victim.kill(None, date, reason)
		else:
			raise GameError(u"%s muss %s in Runde %s gar nicht umbringen!" % (killer.player.name, victim.player.name, self.name))
			
	def getParticipantsStartingWith(self, participant_or_player):
		"""Returns a list of all Participants in this Round, starting with
		the Participant or Player given.
		Returns None if the player is not found.
		"""
		index = 0
		found = False
		for participant in self.participants:
			if participant.id == participant_or_player.id or \
				participant.player.id == participant_or_player.id or \
				participant.player.public_id == participant_or_player.id:
				found = True;
				break
			index += 1
		if not found:
			return None
		ret = []
		ret.extend(self.participants[index:])
		ret.extend(self.participants[:index])
		return ret
	
	def getDeadParticipants(self):
		"""Returns a list of dead Participants"""
		participants = [ p for p in self.participants if not p.alive() ]
		participants.sort(key = lambda p: str(p.killedby.date))
		return participants
		
	def getLivingParticipants(self):
		"""Returns a list of alive Participants"""
		participants = [ p for p in self.participants if p.alive() ]
		participants.sort(key = lambda p: p.player.name + p.player.info)
		return participants
	
	def getInitialVictim(self, participant_or_player ):
		"""Returns the victim of the given Participant or Player as a
		Participant object.
		"""
		preparedlist = self.getParticipantsStartingWith(participant_or_player)
		if preparedlist is None:
			return None
		return preparedlist[1]
	
	def getCurrentVictim(self, participant_or_player):
		for p in self.getParticipantsStartingWith(participant_or_player)[1:]:
			if p.alive():
				return p
		return None
	
	def getCurrentKiller(self, participant_or_player):
		for p in reversed(self.getParticipantsStartingWith(participant_or_player)[1:]):
			if p.alive():
				return p
		return None
	
	def getInitialKiller(self, participant_or_player):
		preparedlist = self.getParticipantsStartingWith(participant_or_player)
		if preparedlist is None:
			return None
		return preparedlist[-1]
	
	def canKill(self, killer, victim):
		"""Returns true if killer.getInitialVictim() == victim or the killer is None
		(because a Game Master kill is always possible)
		"""
		if killer is None:
			return True
		p = self.getParticipantsStartingWith(killer)
		if p is not None:
			for participant in p[1:]:
				if not participant.alive():
					continue
				else:
					ret = (participant.alive() and (participant.id == victim.id or participant.player.id == victim.id))
					return ret
		return False
	
	def canRevert(self, victim):
		"""Returns True if the victim's death can be reverted, i.e. the kill
		is at the end of a chain. Returns also False if the victim in question 
		is still alive or does not exist in this round."""
		if victim is None:
			return False
		l = self.getParticipantsStartingWith(victim)
		if l is not None:
			return l[1].alive()
		else:
			return False
	
	def shuffle(self, participants):
		random.shuffle(participants)
		infos = defaultdict(list)
		for p in participants:
			infos[p.player.info].append(p)
		ret = []
		for lst in [ l[1] for l in sorted(infos.items(), key=lambda l: len(l[1])) ]:
			if len(ret) == 0:
				ret = lst
			elif len(lst) >= len(ret):
				for a in sorted(random.sample(xrange(len(lst)), len(ret)), reverse=True):
					lst.insert(a, ret.pop())
				ret = lst
			else:
				for a in sorted(random.sample(xrange(len(ret)), len(lst)), reverse=True):
					ret.insert(a, lst.pop())
		participants = ret
		return participants
		
	
	def start(self, players, rounds):
		"""Starts the Round. Called by Game.start(). Calling it from elsewhere 
		does not make sense.
		"""
		# get all rounds that are populated yet into a list
		roundstocheck = []
		for name,round in rounds.iteritems():
			if len(round.participants) > 0 and not round == self:
				roundstocheck.append(round)
		# init own list
		self.participants = [ Participant(player, self) for player in players ]
		# shuffle own list
		self.participants = self.shuffle(self.participants)
		# check if any players would have to kill the same other player in multiple rounds.
		# the len comparison is a safeguard to avoid an infinite shuffling loop 
		if len(roundstocheck)+5 < len(players):
			iterations = 1
			while iterations < (len(players)):
				reshuffles = set()
				for k in self.participants:
					for round in roundstocheck:
						if round.getInitialVictim(k.player) is not None and self.getInitialVictim(k.player).player.id == round.getInitialVictim(k.player).player.id:
							reshuffles.add(k)
				for k in self.participants:
					# TODO: analyze info buckets. if not enough buckets, it shouldn't be a constraint.
					if len(k.player.info) > 1 and self.getInitialVictim(k).player.info == k.player.info:
						reshuffles.add(k)
				if len(reshuffles) == 0:
					break
				for k in reshuffles:
					self.participants.remove(k)
				for k in reshuffles:
					self.participants.insert( max(len(self.participants)-1, random.randint(0, len(self.participants))), k )
				iterations += 1



class Config:
	def __init__(self):
		self.__setstate__({})
	def __setstate__(self, state):
		"""Upgrade old pickles/init defaults."""
		for (key, default) in [
				('timezone', "Europe/Berlin"),
				('twitter', True),
				('adminisplaying', False)
			]:
			if not state.has_key(key):
				state[key] = default
		self.__dict__.update(state)

class Game:
	"""Main Class and API entrance for a Moerderspiel Game. Each game on a
	server has it's own Game instance, containing completely independent
	Rounds and Players.
	
	TODO: Elaborate on the structure and stati of the game object
	
	Attributes:
		* ``status``: Current status of the Game. May be 'OPEN' (for player
			registration), 'RUNNING' or 'OVER'.
		* ``name``: The name of the game.
		* ``id``: To access the game, you need to know this game ID.
		* ``mastercode``: Authentication Code for the Game Master.
		* ``enddate``: datetime object to mark the end time.
		* ``rounds``: dictionary containing the rounds (key = round name)
		* ``players``: list of Players in this Game.
	"""
	def __init__(self, name, rounds, enddate, url, rundenid='', desc=None, gamemastermail=None):
		self.status = 'OPEN'
		self.name = name
		self.id = ''
		if len(rundenid) > 2 and len(rundenid) < 21:
			id = rundenid.lower().strip()
			for c in list(id):
				if c in 'abcdefghijklmnopqrstuvwxyz0123456789-_.':
					self.id += c
			if len(rundenid) <= 2:
				self.id = wordconstruct.WordGenerator().generate(7)
		else:
			self.id = wordconstruct.WordGenerator().generate(7)
		self.mastercode = wordconstruct.WordGenerator().generate(6)
		self.enddate = force_datetime(enddate)
		self.rounds = {}
		self.players = []
		self.url = url
		self.desc = desc
		self.config = Config()
		self.gamemastermail = gamemastermail
		for a in range(rounds):
			self.rounds[str(a+1)] = Round(str(a+1))
		if rundenid.startswith("test") and not isinstance(self, MultiGame):
			self.addTestPlayers()
	def __str__(self):
		return u'Spiel: %s\nid: %s\nstatus: %s\nmastercode: %s\nenddate: %s\nplayers: %s\nrounds: %s' % (self.name, self.id, self.status, self.mastercode, self.enddate, self.players, self.rounds)
	def __setstate__(self, state):
		"""Upgrade old pickles."""
		for (key, default) in [
				('config', Config()),
				('desc', None),
				('gamemastermail', None)
			]:
			if not state.has_key(key):
				state[key] = default
		self.__dict__.update(state)
	
	def addTestPlayers(self):
		for name, info in utils.random_playerdata(20):
			self.addPlayer(name, info)
			
	def makeTestKills(self):
		for round in self.rounds.values():
			killtime = datetime.now() - timedelta(minutes=len(round.participants)*5)
			for participant in random.sample(round.participants, random.randint(len(round.participants)/8, len(round.participants)/2)):
				killtime = killtime + timedelta(minutes=random.randint(0,10))
				participant.kill(round.getCurrentKiller(participant), killtime, u"Aus Gründen umgebracht.")
	
	def addPlayer(self, name, info, email=''):
		"""Add a player to the player list using the given name and info.
		The info text is dedicated to any additional information for identifying
		a player in case of name clashes.
		
		Raises a GameError if the registration phase is over or the name length
		is 1 or lower.
		"""
		if self.status != 'OPEN':
			raise GameError(u'Spiel ist nicht (mehr) in der Registrierungsphase')

		if len(name) == 0:
			raise GameError(u'Der Spieler sollte auch einen Namen haben')
			
		if len(email) > 0 and email in [ p.email for p in self.players ]:
			raise GameError(u'Sorry, diese Emailadresse ist schon drin...')
			
		if len(email) < 5 and self.config.adminisplaying:
			raise GameError(u'Sorry, da der Game Master mitspielt, können wir nicht auf Email verzichten.')
			
		if (name, info) in [ (p.name, p.info) for p in self.players ]:
			raise GameError(u'Dieser Name in Verbindung mit der Zusatzinfo ist schon drin... also, wenn da wirklich zwei mit exakt dem selben Namen sind, bitte beim Spielleiter melden!')
			
		self.players.append(Player(name, info, self, email))
	
	def sendgamemastermail(self, templatefilename="welcomegamemaster.txt", subject=u"Mörderspiel %s wurde eröffnet!"):
		if self.gamemastermail is None or len(self.gamemastermail) < 5:
			return
		utils.sendemail(
			self.templatedir,
			templatefilename, 
			subject % self.id,
			'hades@moerderspiel.org',
			self.gamemastermail,
			self
		)
		
	
	def removePlayer(self, player_id):
		"""Removes a player using the player's ID/Code.
		
		Raises a GameError if the game isn't in the registration phase 
		(game.status != 'OPEN') or the player is not found by the given ID.
		"""
		if self.status == 'OPEN':
			for p in self.players:
				if p.id == player_id or p.public_id == player_id:
					self.players.remove(p)
					return
		else:
			raise GameError(u'Sorry, das Spiel ist nicht (mehr) in der Registrierungsphase')
		raise GameError(u'Spieler-ID %s nicht gefunden' % player_id)
	
	def kickPlayer(self, player_id, mastercode):
		"""Kicks the player identified by player_id from the running game 
		(Game Master action).
		
		Raises a GameError if the mastercode is wrong or the game is over.
		Forwards GameErrors from Round.kill()
		"""
		if self.status == 'RUNNING' or self.status == 'OVER':
			if mastercode == self.mastercode: 
				for r in self.rounds.values():
					for participant in r.participants:
						if participant.player.id == player_id or participant.player.public_id == player_id:
							try:
								r.kill(None, participant.id, 'never', u'Premature End Of Game')
								r.getCurrentKiller(participant).player.sendemail()
							except:
								pass
							break
			else:
				raise GameError(u'Das war nicht der Mastercode!')
		else:
			raise GameError(u'Sorry, das Spiel läuft noch nicht.')
	
	def kill(self, killer_public_id, victim_id, date, reason):
		"""Kills a victim.
		Needs the killer's player.public_id (taken from an option list in 
		the UI) and the victim's Participant.id (taken from the kill 
		assignment). Date and reason are to be entered in the kill form in UI.
		
		Raises a GameError if game.status != 'RUNNING'.
		Forwards GameErrors from Round.kill().
		"""
		if self.status == 'RUNNING':
			errors = 0;
			for key,round in self.rounds.iteritems():
				try:
					round.kill(killer_public_id, victim_id, date, reason)
					if killer_public_id is not None:
						self.findPlayer(killer_public_id).sendemail()
					elif round.hasParticipant(victim_id):
						round.getCurrentKiller(round.getParticipant(victim_id)).player.sendemail()							
					round.getParticipant(victim_id).player.sendemail()
					if self.config.twitter:
						twitkill(round.getParticipant(victim_id))
				except GameError as e:
					errors += 1
			if errors == len(self.rounds):
				raise GameError(u'Signaturcode ungültig')
		else:
			raise GameError(u'Sorry, das Spiel läuft nicht (mehr).')
	
	def findParticipant(self, id):
		"""Finds a Participant by his ID/Code in all rounds. Returns None if
		not found.
		"""
		for round in self.rounds:
			for participant in self.rounds[round].participants:
				if participant.id == id:
					return participant
		return None
	
	def findPlayer(self, player_or_participant_or_id):
		if isinstance(player_or_participant_or_id, Player):
			return player_or_participant_or_id
		elif isinstance(player_or_participant_or_id, Participant):
			return player_or_participant_or_id.player
		elif isinstance(player_or_participant_or_id, basestring):
			for player in self.players:
				if (player.public_id == player_or_participant_or_id or
					player.id == player_or_participant_or_id):
					return player
			for participant in flatten([ r.participants for r in self.rounds.values()]):
				if (participant.player.id == player_or_participant_or_id or
					participant.player.public_id == player_or_participant_or_id ):
					return participant.player
		return None

	def canRevert(self, victim_participant_or_id):
		ret = False
		for key,round in self.rounds.iteritems():
			if round.canRevert(victim_participant_or_id):
				ret = True
		return ret
	
	def revertkill(self, victim_participant_or_id):
		vp = None
		if isinstance(victim_participant_or_id, Participant):
			vp = victim_participant_or_id
		elif isinstance(victim_participant_or_id, basestring):
			vp = self.findParticipant(victim_participant_or_id)
		if isinstance(vp, Participant) and self.canRevert(vp):
			killer = vp.killedby.killer.player
			vp.killedby = None
			victim = vp.player
			killer.sendemail()
			victim.sendemail()
		else:
			raise GameError(u'Can\'t touch this! Der Mord ist nicht am Ende einer Mordkette. Es müssten erst Folgemorde zurückgenommen werden.')
	
	def findPlayerByPublicID(self, id):
		"""Finds a Player by his public_id. Returns None if not found.
		"""
		for player in self.players:
			if player.public_id == id:
				return player
		return None
	
	def getMassMurderer(self):
		"""Returns a dict consisting of a high score and a list of Players
		that met this high score:
			{ 'kills' : int, 'killers' : list(Player) }
		This will at times result in returning all players, none of whom have 
		scored any kill.
		"""
		##import ipdb; ipdb.set_trace()
		allparticipants = flatten([ r.participants for r in self.rounds.values() ])
		kills = [ p.killedby for p in allparticipants if p.killedby is not None ]
		killlist = [ k.killer for k in kills if k.killer is not None]
		killerlist = [ k.player for k in killlist ]
		c = {}
		for i in killerlist:
			c[i] = c.get(i,0) + 1
		sortedlist = sorted([ (freq,word) for word, freq in c.items() ], reverse=True)
		massmurdererlist = [ p for p in sortedlist if p[0] == sortedlist[0][0] ]
		if len(massmurdererlist) > 0:
			return dict(kills=sortedlist[0][0], killers=[ i[1] for i in massmurdererlist ])
		else:
			return []
	
	
	def getMassMurdererString(self, maxlen=45):
		"""Returns a text consisting of a comma-separated list of Player
		names who are currently in the lead, adding the score in parentheses:
		'Anna, Berta, Charlie (4)'
		If this String would be longer than maxlen (default: 40), then the
		number of leading players is returned (This means that it may display
		the total number of players, but none of them scored yet).
		"""
		mm = self.getMassMurderer()
		if len(mm) < 1:
			return "Niemand"
		ret = ', '.join([ i.name for i in mm['killers']])
		ret += ' (%s Morde)' % mm['kills']
		if len(ret) > maxlen:
			ret = u'%s Mörder (%s Morde)' % (len(mm['killers']), mm['kills'])
		return ret

	def getHighScoreList(self):
		playerlist = sorted(flatten([p.player for p in [r for r in self.rounds.values()].pop().participants]), key=lambda q: self.getScore(q), reverse=True)
		highscore = self.getScore(playerlist[0])
		return sorted([ p for p in playerlist if self.getScore(p) == highscore ], key=lambda q: q.name+q.info)
			
	def getHighScoreString(self, maxlen=45):
		hs = self.getHighScoreList()
		if len(hs) < 1:
			return "Niemand"
		ret = ', '.join([ p.name for p in hs])
		ret += ' (%s Punkte)' % hs[0].score()
		if len(ret) > maxlen:
			ret = u'%s Spieler (%s Punkte)' % (len(hs), hs[0].score())
		return ret
		
	def getScore(self, player):
		return len([ r for r in self.rounds.values() if r.hasParticipant(player) ]) - self.getDeathsCount(player) + self.getKillsCount(player)
		
	def getKilled(self):
		return sorted(flatten([[ p for p in r.getDeadParticipants() if p.killedby.killer is not None] for r in self.rounds.values() ]), key=lambda r: str(r.killedby.date), reverse=True)
	
	def getKillsCount(self, player_or_participant_or_id):
		id = self.findPlayer(player_or_participant_or_id)
		return len( [ p for p in flatten([ r.getDeadParticipants() for r in self.rounds.values() ]) if p.killedby.killer and p.killedby.killer.player.id == id.id ] )
	
	def getDeathsCount(self, player_or_participant_or_id):
		id = self.findPlayer(player_or_participant_or_id).id
		return len( [ p for p in flatten([ r.participants for r in self.rounds.values() ]) if p.killedby and p.player.id == id ])
	
	def start(self, mastercode):
		"""Starts the game. Needs the Mastercode.
		"""
#		if self.status == 'OPEN' and mastercode == self.mastercode:
		if mastercode == self.mastercode:
			if len(self.players) < 3:
				raise GameError(u'Das Spiel startet nicht mit weniger als 3 Spielern.')
			for ro in self.rounds:
				self.rounds[ro].start( self.players, self.rounds )
			self.status = 'RUNNING'
			for p in self.players:
				p.sendemail()
		else:
			raise GameError(u'Das war nicht der Mastercode')
		if self.id.startswith('test'):
			self.makeTestKills()
	
	def stop(self, mastercode):
		"""Stops the game.
		"""
		if mastercode == self.mastercode:
			self.status = 'OVER'
		else:
			raise GameError(u'Das war nicht der Mastercode')
			
	def generate_all_gamemasterkill_substitutes(self):
		self.pdfgen(participants = [ item.getCurrentKiller() for l in [ r.getDeadParticipants() for r in g.rounds.values() ] for item in l if item.killedby.killer is None ] )
		
	def pdfgen(self, players = None, participants = None):
		fname = self.id
		if( players is None ):
			players = self.players
		if( len(players) == 0 ):
			return
		elif( len(players) == 1 ):
			fname = self.id + '_' + players[0].public_id
		if participants is not None:
			fname = self.id + '_gamemaster'
		tmptexdir = "/tmp/moerder_" + fname
		if not os.path.isdir(tmptexdir):
			os.mkdir(tmptexdir)
		tmplfile = "moerder.tex"
		if( len(self.rounds) % 2 == 0 and len(players) > 1 ):
			tmplfile = "moerder2.tex"
		shutil.copyfile(os.path.join(self.templatedir, tmplfile), os.path.join(tmptexdir, "moerder.tex"))
		listfile = codecs.open(os.path.join(tmptexdir, "list.tex"), "w", "utf-8")
		#for roundid,round in self.rounds.iteritems():
		#	for participant in round.participants:
		#		killer = participant.player
		#		victim = round.getInitialVictim(participant).player
		for killer in sorted(players, key=lambda x: x.name):
			assignments = 0
			for roundid,round in self.rounds.iteritems():
				participant = round.getParticipant(killer)
				if participant is not None and participant.alive() and (participants is None or participant in participants):
					victim = round.getCurrentVictim(killer)
					if victim is not None:
						roundname = round.name if len(self.rounds) > 1 else ''
						#listfile.write("\Auftrag{Gamename}{Gameid}{Victim}{Killer}{Signaturecode}{Spielende}{URL}\n")
						listfile.write(u"\\Auftrag{%s}{%s}{%s\\\\%s}{%s\\\\%s}{%s}{%s}{%s}{%s}\n" % 
							(
								utils.latexEsc(self.name),
								utils.latexEsc(self.id), 
								utils.latexEsc(victim.player.name), 
								utils.latexEsc(victim.player.info), 
								utils.latexEsc(killer.name), 
								utils.latexEsc(killer.info), 
								utils.latexEsc(victim.id), 
								utils.latexEsc(self.enddate.strftime("%d.%m.%Y %H:%M")), 
								utils.latexEsc(self.url), 
								utils.latexEsc(roundname)
							)
						)
						assignments += 1
					elif len(players) == 1:
						listfile.write(u"%s hat kein Opfer mehr in Kreis %s.\\\\~\\\\~" % (utils.latexEsc(killer.name), round.name))
				elif len(players) == 1:
					#listfile.write(u"%s lebt nicht mehr in Kreis %s.\\\\~\\\\~" % (utils.latexEsc(killer.name), round.name))
					pass
			if assignments > 3:
				listfile.write(u"\\pagebreak\n")
		listfile.close()
		cwd = os.getcwd()
		os.chdir(tmptexdir)
		os.system("xelatex moerder.tex")
		os.chdir(cwd)
		pdfpath = os.path.join(self.savegamedir, "%s.pdf" % fname)
		shutil.copyfile(tmptexdir + "/moerder.pdf", pdfpath)
		return pdfpath


class MultiGame(Game):
	def __init__(self, name, rounds, enddate, url, rundenid='', desc=None, gamemastermail=None):
		Game.__init__(self, name, rounds, enddate, url, rundenid, desc, gamemastermail)
		self.games = {}
		self.roundcount = rounds
		r = {}
		self.myrounds = []
		for k,v in self.rounds.iteritems():
			v.name = "%s-%s" % (self.id, k)
			r[v.name] = v
			self.myrounds.append(v.name) 
		self.rounds = r
		if rundenid.startswith("test"):
			for gameid,gamename in [('subgame1', "Unterspiel1"), ('subgame2', "Unterspiel2"), ('subgame3', "Unterspiel3")]:
				self.addGame(self.mastercode, gameid, gamename)
			self.addTestPlayers()
			
	def __str__(self):
		return u'MultiSpiel: %s\nid: %s\nstatus: %s\nmastercode: %s\nenddate: %s\nplayers: %s\nrounds: %s' % (self.name, self.id, self.status, self.mastercode, self.enddate, self.players, self.rounds)
	
	def addTestPlayers(self):
		for name, info in utils.random_playerdata(40):
			self.addPlayer(name, info, subgame=random.sample(self.games.keys(), 1)[0])

	def addPlayer(self, name, info, email='', subgame=''):
		"""Add a player to the player list using the given name and info.
		The info text is dedicated to any additional information for identifying
		a player in case of name clashes.
		
		Raises a GameError if the registration phase is over or the name length
		is 1 or lower.
		"""
		if not subgame in self.games.keys():
			raise GameError("Kein existentes Unterspiel angegeben.")
		try:
			Game.addPlayer(self, name, info, email)
			self.players[-1].subgame = subgame
		except:
			raise
	
	def addGame(self, mastercode, rundenid, name, desc=''):
		if self.status == 'OPEN' and mastercode == self.mastercode:
			gameid = ''
			if len(rundenid) > 2 and len(rundenid) < 21:
				id = rundenid.lower().strip()
				for c in list(id):
					if c in 'abcdefghijklmnopqrstuvwxyz0123456789-_.':
						gameid += c
				if len(gameid) <= 2:
					gameid = wordconstruct.WordGenerator().generate(7)
			else:
				gameid = wordconstruct.WordGenerator().generate(7)
			subgame = Game(name, self.roundcount, self.enddate, self.url, gameid, desc, None)
			for k,v in subgame.rounds.iteritems():
				v.name = "%s-%s" % (subgame.id, k)
				self.rounds[v.name] = v
			subgame.players = self.players
			self.games[gameid] = subgame
		else:
			raise GameError(u'Das war nicht der Mastercode')
	
	def getMassMurderer(self):
		"""Returns a dict consisting of a high score and a list of Players
		that met this high score:
			{ 'kills' : int, 'killers' : list(Player) }
		This will at times result in returning all players, none of whom have 
		scored any kill.
		"""
		##import ipdb; ipdb.set_trace()
		allparticipants = flatten([ r.participants for r in self.rounds.values() ])
		kills = [ p.killedby for p in allparticipants if p.killedby is not None ]
		killlist = [ k.killer for k in kills if k.killer is not None]
		killerlist = [ k.player for k in killlist ]
		c = {}
		for i in killerlist:
			c[i] = c.get(i,0) + 1
		sortedlist = sorted([ (freq,word) for word, freq in c.items() ], reverse=True)
		massmurdererlist = [ p for p in sortedlist if p[0] == sortedlist[0][0] ]
		if len(massmurdererlist) > 0:
			return dict(kills=sortedlist[0][0], killers=[ i[1] for i in massmurdererlist ])
		else:
			return []

	def getScore(self, player):
		if player is not Player:
			player = self.findPlayer(player)
		return len([ r for r in self.rounds.values() if r.hasParticipant(player) ]) - self.getDeathsCount(player) + self.getKillsCount(player)

	def getHighScoreList(self):
		playerlist = sorted(flatten([p.player for p in [r for r in self.rounds.values() ].pop().participants]), key=lambda q: self.getScore(q), reverse=True)
		highscore = self.getScore(playerlist[0])
		return sorted([ p for p in playerlist if self.getScore(p) == highscore ], key=lambda q: q.name+q.info)
			
	def getKillsCount(self, player_or_participant_or_id):
		player = self.findPlayer(player_or_participant_or_id)
		return len( [ p for p in flatten([ r.getDeadParticipants() for r in self.rounds.values() ]) if p.killedby.killer and p.killedby.killer.player.id == player.id ] )
	
	def getDeathsCount(self, player_or_participant_or_id):
		id = self.findPlayer(player_or_participant_or_id).id
		return len( [ p for p in flatten([ r.participants for r in self.rounds.values() ]) if p.killedby and p.player.id == id ])

	def start(self, mastercode):
		"""Starts the game. Needs the Mastercode.
		"""
		if mastercode == self.mastercode:
			if len(self.players) < 3:
				raise GameError(u'Das Spiel startet nicht mit weniger als 3 Spielern.')
			for roundid,round in self.rounds.iteritems():
				round.start( [ p for p in self.players if roundid.startswith(p.subgame) or roundid in self.myrounds ], self.rounds )
			self.status = 'RUNNING'
			for game in self.games.values():
				game.status = 'RUNNING'
			for p in self.players:
				p.sendemail()
		else:
			raise GameError(u'Das war nicht der Mastercode')
		if self.id.startswith('test'):
			self.makeTestKills()
	
	def stop(self, mastercode):
		"""Stops the game.
		"""
		Game.stop(self, mastercode)
		for game in self.games.values():
			game.status = 'OVER'
		
