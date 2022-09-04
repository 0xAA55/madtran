#!/usr/bin/env python3
# -*- coding: utf-8 -*
import json

ctdict = {}
cedict = {}
tedict = {}
firstchars = set()
cedict_maxkeylen = 1
tedict_maxkeylen = 1
with open("cedict_database.py", "w", encoding="utf-8") as fw:
	with open("cedict.txt", "r", encoding="utf-8") as fr:
		for line in fr:
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
	fw.write('#!/usr/bin/env python3\n')
	fw.write('# -*- coding: utf-8 -*\n')
	fw.write('ctdict = %s\n' % (str(ctdict)))
	fw.write('cedict = %s\n' % (str(cedict)))
	fw.write('tedict = %s\n' % (str(tedict)))
	fw.write('firstchars = %s\n' % (str(firstchars)))
	fw.write('cedict_maxkeylen = %d\n' % (cedict_maxkeylen))
	fw.write('tedict_maxkeylen = %d\n' % (tedict_maxkeylen))

with open("cedict.json", "w", encoding="utf-8") as fw:
	json.dump(cedict, fw, indent=4, ensure_ascii=False)

with open("tedict.json", "w", encoding="utf-8") as fw:
	json.dump(tedict, fw, indent=4, ensure_ascii=False)

ctdict ={tc: list(scs) for tc, scs in ctdict.items()}
with open("cedict_meta.json", "w", encoding="utf-8") as fw:
	meta = {
		"ctdict": ctdict,
		"firstchars": "".join(firstchars),
		"cedict_maxkeylen": cedict_maxkeylen,
		"tedict_maxkeylen": tedict_maxkeylen
	}
	json.dump(meta, fw, indent=4, ensure_ascii=False)
