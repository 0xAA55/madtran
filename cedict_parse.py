#!/usr/bin/env python3
# -*- coding: utf-8 -*
import os
import json
import sqlite3

def load_zipart():
	zi_parts = {}
	with open(os.path.join("ids_db", "ids_lv2.txt"), "r", encoding="utf-8") as fr:
		for line in fr:
			line = line.strip()
			if line[0] == '#': continue
			zi, ids = line.split('\t', 1)
			ids = ids.replace(';', '\t')
			ids = ids.replace('⿰', '')
			ids = ids.replace('⿱', '')
			ids = ids.replace('⿲', '')
			ids = ids.replace('⿳', '')
			ids = ids.replace('⿴', '')
			ids = ids.replace('⿵', '')
			ids = ids.replace('⿶', '')
			ids = ids.replace('⿷', '')
			ids = ids.replace('⿼', '')
			ids = ids.replace('⿸', '')
			ids = ids.replace('⿹', '')
			ids = ids.replace('⿺', '')
			ids = ids.replace('⿽', '')
			ids = ids.replace('⿻', '')
			ids = ids.replace('⿿', '')
			ids = ids.replace('⿾', '')
			ids = ids.split('\t')
			try:
				zi_parts[zi] += ids
			except KeyError:
				zi_parts[zi] = ids
	return zi_parts

if __name__ == '__main__':
	os.chdir(os.path.dirname(os.path.realpath(__file__)))
	ctdict = {}
	cedict = {}
	tedict = {}
	firstchars = set()
	cedict_maxkeylen = 1
	tedict_maxkeylen = 1
	with open("cedict.txt", "r", encoding="utf-8") as fr:
		for line in fr:
			line = line.strip()
			if line[0] == '#': continue
			cut = line.split(' ', 2)
			tc = cut[0]
			sc = cut[1]
			cut = cut[2].split(']', 1)
			pron = cut[0].strip()
			expl = cut[1].strip()
			if pron[0] != '[':
				print("奇怪的发音格式：%s：%s]" % (sc, pron))
			else:
				pron = pron[1:]
			if len(expl) >= 2 and ("%s%s" % (expl[0], expl[-1])) == '//':
				expl = expl[1:-1].replace(';', '/').split('/')
			else:
				print("奇怪的解释格式：%s：%s" % (sc, expl))
				expl = [expl]
			expl = [ e.strip() for e in expl ]

			if sc != tc:
				try:
					ctdict[tc] |= {sc}
				except KeyError:
					ctdict[tc] = {sc}
				firstchars |= {tc[0]}

			try:
				scdata = cedict[sc]
			except KeyError:
				scdata = {}
			try:
				prondata = scdata[pron]
			except KeyError:
				prondata = []
			prondata.extend(expl)
			scdata[pron] = prondata
			cedict[sc] = scdata

			try:
				tcdata = tedict[tc]
			except KeyError:
				tcdata = {}
			try:
				prondata = tcdata[pron]
			except KeyError:
				prondata = []
			prondata.extend(expl)
			tcdata[pron] = prondata
			tedict[tc] = tcdata

			firstchars |= {sc[0]}
			cedict_maxkeylen = max(cedict_maxkeylen, len(sc))
			tedict_maxkeylen = max(tedict_maxkeylen, len(tc))

	with open("cedict.json", "w", encoding="utf-8") as fw:
		json.dump(cedict, fw, indent=4, ensure_ascii=False)

	with open("tedict.json", "w", encoding="utf-8") as fw:
		json.dump(tedict, fw, indent=4, ensure_ascii=False)

	con = sqlite3.connect("madtran.db")
	cur = con.cursor()
	cur.execute("DROP TABLE IF EXISTS ctdict")
	cur.execute("DROP TABLE IF EXISTS cedict")
	cur.execute("DROP TABLE IF EXISTS tedict")
	cur.execute("DROP TABLE IF EXISTS firstchars")
	cur.execute("DROP TABLE IF EXISTS metadata")
	cur.execute("CREATE TABLE ctdict(tc TEXT PRIMARY KEY NOT NULL, sc TEXT NOT NULL)")
	cur.execute("CREATE TABLE cedict(sc TEXT PRIMARY KEY NOT NULL, scdata TEXT NOT NULL)")
	cur.execute("CREATE TABLE tedict(tc TEXT PRIMARY KEY NOT NULL, tcdata TEXT NOT NULL)")
	cur.execute("CREATE TABLE firstchars(chr TEXT PRIMARY KEY NOT NULL)")
	cur.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY NOT NULL, value INT NOT NULL)")
	try:
		cur.execute("CREATE TABLE zipart(zi TEXT PRIMARY KEY NOT NULL, ids TEXT NOT NULL)")
		zi_parts = load_zipart()
		for zi, ids in zi_parts.items():
			cur.execute("INSERT INTO zipart(zi, ids) VALUES(?,?)", (zi, '\t'.join(ids)))
	except sqlite3.OperationalError as e:
		if str(e) == 'table zipart already exists':
			pass
		else:
			raise e
	for tc, sc in ctdict.items():
		cur.execute("INSERT INTO ctdict(tc,sc) VALUES(?,?)", (tc, '\n'.join(list(sc))))
	splitter = '/'
	for sc, scdata in cedict.items():
		cur.execute("INSERT INTO cedict(sc,scdata) VALUES(?,?)", (sc, '\n'.join([f'{k}\t{splitter.join(v)}' for k, v in scdata.items()])))
	for tc, tcdata in tedict.items():
		cur.execute("INSERT INTO tedict(tc,tcdata) VALUES(?,?)", (tc, '\n'.join([f'{k}\t{splitter.join(v)}' for k, v in tcdata.items()])))
	for ch in firstchars:
		cur.execute("INSERT INTO firstchars(chr) VALUES(?)", (ch))
	cur.execute("INSERT INTO metadata(key,value) VALUES(?,?)", ('cedict_maxkeylen', cedict_maxkeylen))
	cur.execute("INSERT INTO metadata(key,value) VALUES(?,?)", ('tedict_maxkeylen', tedict_maxkeylen))
	con.commit()

	ctdict ={tc: list(scs) for tc, scs in ctdict.items()}
	with open("cedict_meta.json", "w", encoding="utf-8") as fw:
		meta = {
			"ctdict": ctdict,
			"firstchars": "".join(firstchars),
			"cedict_maxkeylen": cedict_maxkeylen,
			"tedict_maxkeylen": tedict_maxkeylen
		}
		json.dump(meta, fw, indent=4, ensure_ascii=False)
