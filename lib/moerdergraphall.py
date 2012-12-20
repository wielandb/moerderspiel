#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os.path
import yapgvb as graph
import textwrap
import math
import colorsys
import pickle
from moerderklassen import *

def u8(s):
	try:
		return s.decode('utf8')
	except UnicodeDecodeErrors:
		try:
			return s.decode('latin1')
		except UnicodeDecodeError:
			return None

def colorgen(starthue):
	PHI = (1.0 + math.sqrt(5)) / 2.0
	s = 1.0
	v = 1.0
	c = 0
	while(True):
		r,g,b = colorsys.hsv_to_rgb(starthue, s, v)
		starthue = (starthue + PHI) % 1.0
		c += 1
		if c % 3 == 0:
			v = (v + PHI) % 1.0
		yield '#%02x%02x%02xA0' % ( r*255, g*255, b*255 )

def moerdergraphall(game, filename, alledges=False, nodefontsize=8.0, edgefontsize=8.0):
	# G is the main Graph object
	G = graph.Digraph("Moerder")
	G.model = 'subset'
	G.overlap = 'compress'
	G.splines = True
	G.normalize = True
	G.packmode = 'graph'
	G.rankdir = 'LR'
	# a dict for indexing all nodes
	nodes = {}
	# we need to keep some of the nodes in mind
	prev_node = first_node = node = None
	# make a copy of the participant list so we don't jumble up the original list
	participants = game.rounds.values()[0].participants[:]
	gmnode = G.add_node('Game Master')
	gmnode.label = 'Game Master'
	gmnode.fontsize = nodefontsize
	gmnode.fontname = 'arial'
	gmnode.color = 'gray'
	gmnode.fontcolor = 'gray'
	gmnode.style = 'rounded'
	hnode = inode = G.add_node('invisible')
	inode.style = 'invisible'
	inode.pos = (0.0, 0.0)
	massmurdererlist = [ player.public_id for player in game.getMassMurderer()['killers'] ]

	if not alledges:
		# if not admin/gameover view: sort nodes prior to adding them to the graph
		participants.sort(key = lambda p: p.player.name + p.player.info)
	nodecount = len(participants)
	nodesperline = math.trunc(math.sqrt(nodecount))
	# for each participant, add a node to the graph bearing his name
	nodenumber = 0
	for participant in participants:
		nodenumber += 1
		name = participant.player.name
		if len(participant.player.info) > 0:
			name += "\\n" + participant.player.info
		node = G.add_node(participant.player.public_id)
		node.label = name.encode('utf-8')
		node.fontsize = nodefontsize
		node.style = 'rounded,filled'
		node.penwidth = 2
		node.color = '#00003380'
		node.fillcolor = '#00003322'
		node.margin = 0.01
		nodeweight = game.getDeathsCount(participant) + game.getKillsCount(participant)
		#node.group = str(nodeweight)
		node.pos = ( nodenumber % nodesperline, nodenumber / nodesperline)
		if nodeweight == 0:
			iedge = G.add_edge(inode, node)
			iedge.style = 'invisible'
			iedge.arrowhead = 'none'
			iedge.weight = 0.1
			node.pos = (0.0, 0.0)
			#iedge.constraint = False
		if not prev_node:
			first_node = node
		# put all the nodes into a dict so we could find them fast by the player's id (needed later)
		nodes[participant.player.public_id] = node
		
		prev_node = node
		node.fontname = 'arial'
		# kicked participants are gray
		if participant.killed() and participant.killedby.killer is None:
			#node.color = '#FF6666FF'
			#node.fontcolor = '#33333388'
			#node.fillcolor = '#66666622'
			node.style += ',dashed'
		# mass murderers are black
		if participant.player.public_id in massmurdererlist:
			node.color = 'black'
			node.fillcolor = 'black'
			node.fontcolor = 'white'
		# dead participants are red
		if (game.getDeathsCount(participant) >= len(game.rounds)):
			node.color = '#FF0000FF'
			node.penwidth = 2
			#node.fontcolor = '#FFFFFFFF'
			#node.fillcolor = '#FF0000FF'

	colorgenerator = colorgen(0.86)
	for round in game.rounds.values():
		edgecolor = next(colorgenerator)
		for participant in round.participants:
			if alledges or participant.killed():
				edge = G.add_edge(nodes[participant.getInitialKiller().player.public_id], nodes[participant.player.public_id])
				edge.color = edgecolor
				edge.style = 'dashed'
				edge.penwidth = 2
				edge.weight = 6.0
				#edge.constraint = False
			if participant.killed():
				if not participant.killedby.killer is None:
					# normal case
					edge = G.add_edge(nodes[participant.killedby.killer.player.public_id], nodes[participant.player.public_id])
				else:
					# special case of a game master kill
					edge = G.add_edge(gmnode, nodes[participant.player.public_id])
				edge.color = edgecolor
				edge.fontcolor = 'red'
				edge.style = 'solid'
				edge.penwidth = 4
				edge.weight = 10.0
				# set edge label to kill description
				label = participant.killedby.date + ":\\n"
				maxlinelen = max(24, math.trunc(math.ceil(math.sqrt(6 * len(participant.killedby.reason)))))
				label += "\\n".join(textwrap.wrap(participant.killedby.reason, maxlinelen)).replace('"', "'")
				edge.label = label.encode('utf-8')
				edge.fontsize = edgefontsize
				edge.fontname = 'arial'
	# do the layout math and save to file
	G.layout(graph.engines.dot)
	G.render(filename)


def _loadgame(gamefile):
	input = open(gamefile, 'rd')
	ret = pickle.load(input)
	input.close()
	return ret

if __name__ == "__main__":
	import sys
	game = _loadgame(sys.argv[1])
	moerdergraphall(game, sys.argv[2])
	