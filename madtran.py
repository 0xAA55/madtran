#!/usr/bin/env python3
# -*- coding: utf-8 -*
import Caribe # 需要 Python 有 sqlite3 模块且能安装 torch
import os
import sys
import json
import time
import random
from pypinyin import pinyin, Style

USE_PROXY = True
DEF_PROXY_TYPE = "socks5h"
DEF_PROXY_ADDR = "localhost"
DEF_PROXY_PORT = 1080

try:
	HTTP_PROXY = os.environ['HTTP_PROXY']
	del os.environ['HTTP_PROXY']
except KeyError:
	try:
		HTTP_PROXY = os.environ['http_proxy']
		del os.environ['http_proxy']
	except KeyError:
		HTTP_PROXY = f'{DEF_PROXY_TYPE}://{DEF_PROXY_ADDR}:{DEF_PROXY_PORT}'

try:
	HTTPS_PROXY = os.environ['HTTPS_PROXY']
	del os.environ['HTTPS_PROXY']
except KeyError:
	try:
		HTTPS_PROXY = os.environ['https_proxy']
		del os.environ['https_proxy']
	except KeyError:
		HTTPS_PROXY = HTTP_PROXY

try:
	PROXY_TYPE, PROXY_ADDR_PORT = HTTP_PROXY.split('://', 1)
	PROXY_ADDR, PROXY_PORT = PROXY_ADDR_PORT.split(':', 1)
	PROXY_PORT = int(PROXY_PORT)
except IndexError:
	if len(HTTP_PROXY) == 0:
		USE_PROXY = False
	else:
		print("Parse environ `HTTP_PROXY` failed.")

if __name__ == '__main__':
	cedict_url = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.zip"
	def makepath(filename):
		return os.path.join(os.path.dirname(os.path.realpath(__file__)), filename)
	cedict_zipfile = makepath("cedict_1_0_ts_utf-8_mdbg.zip")
	cedict_member = "cedict_ts.u8"
	cedict_srcfile = makepath("cedict.txt")
	cedict_dbfile = makepath("madtran.db")
	cedict_parser = makepath("cedict_parse.py")
	cedict_updated = False;
	if os.path.exists(cedict_zipfile) and time.time() - os.path.getmtime(cedict_zipfile) > 86400:
		print("正在更新字典。")
		if os.path.exists(cedict_zipfile):
			os.remove(cedict_zipfile)
			if os.path.exists(cedict_member):
				os.remove(cedict_member)
				if os.path.exists(cedict_srcfile):
					os.remove(cedict_srcfile)

	if not os.path.exists(cedict_zipfile):
		import requests
		if USE_PROXY:
			proxies = {
				"http": HTTP_PROXY,
				"https": HTTPS_PROXY
			}
			resp = None
			try:
				resp = requests.get(cedict_url, proxies=proxies)
			except requests.exceptions.ConnectionError as ec:
				print("下载中英字典过程中发生代理连接失败，尝试无代理连接。")
		if resp is None:
			try:
				resp = requests.get(cedict_url)
			except:
				print("下载中英字典失败，HTTP连接失败。")
				exit()
		if 200 <= resp.status_code < 300:
			print("下载字典成功。")
			with open(cedict_zipfile, 'wb') as f:
				resp.raw.decode_content = True
				f.write(resp.content)
		else:
			print(f"下载字典失败：{resp.status_code}：{resp.content}")
			exit()

	if not os.path.exists(cedict_srcfile):
		import zipfile
		with zipfile.ZipFile(cedict_zipfile, 'r') as z:
			z.extract(cedict_member)
		os.rename(cedict_member, cedict_srcfile)
		cedict_updated = True

	if cedict_updated:
		import subprocess
		print("正在解析CEDict")
		subprocess.run([sys.executable, cedict_parser, cedict_dbfile])

import sqlite3
con = sqlite3.connect(cedict_dbfile)
cur = con.cursor()
try:
	ctdict = {k: set(v.split('\n')) for k, v in cur.execute("SELECT * FROM ctdict").fetchall()}
	cedict = {k: {kp:kc.split('/') for kp, kc in [p_c.split('\t') for p_c in v.split('\n')]} for k, v in cur.execute("SELECT * FROM cedict").fetchall()}
	zipart = {k: v.split('\t') for k, v in cur.execute("SELECT * FROM zipart").fetchall()}
	firstchars = {t[0] for t in cur.execute("SELECT * FROM firstchars").fetchall()}
	cedict_maxkeylen = cur.execute("SELECT * FROM metadata WHERE key='cedict_maxkeylen'").fetchall()[0][1]
except sqlite3.OperationalError as e:
	print(f'Size of database: {os.path.getsize(cedict_dbfile)}')
	os.remove(cedict_dbfile)
	print(e)
	exit(1)

pruned = set()
extended = set()
redirected = set()
removed_expl = set()
redirect_chosen = set()

def remove_parenthesis(comment, parenthesis="()"):
	result = ""
	while True:
		cut = comment.split(parenthesis[0], 1)
		result += cut[0] + " "
		if len(cut) == 2:
			try:
				comment = cut[1].split(parenthesis[1], 1)[1] + " "
			except IndexError:
				break
		else:
			break
	return result.replace("  ", " ").strip()

def extract_quoteds(comment, quote = '"'):
	a = comment.split('"')
	return [a[i * 2 + 1] for i in range(len(a) // 2)]

def get_starting_nonascii(comment):
	for i in range(len(comment)):
		if ord(comment[i]) <= 127:
			return comment[:i]
	return comment

def lookup(word):
	try:
		scwords = ctdict[word]
	except KeyError:
		scwords = [word]
	for word in scwords:
		try:
			return cedict[word]
		except KeyError:
			pass

def get_related_words(word):
	related = set()
	keys = list(cedict.keys() | ctdict.keys())
	keys.sort(key=len)
	curlen = len(word)
	for key in keys:
		if key.startswith(word) and key != word:
			newlen = len(key)
			if newlen > curlen and len(related) > 0:
				break
			related |= {key}
			curlen = newlen
	return related

also_checkers = [ "variant of ", "equivalent of ", "equivalent: ", "see ", "see also ", "also written "]
unwant_checkers = [
	'CL:',
	'pr.',
	'used in ',
	'used before ',
	'abbr. ',
	'[', ']', '|',
	'classifier',
	'interjection of ',
	'Kangxi radical ',
	'radical in Chinese',
	'opposite:',
	'courtesy or style name traditionally given to males aged 20 in dynastic China',
	'prefix for ',
	'suffix used ',
	'noun suffix',
	'diminutive suffix',
	'as suffix ',
	'nominalizing suffix',
	'adjective suffix',
	'verb suffix',
	'ship suffix',
	'interjection indicating'
]
relation_checkers = [('单', 'unit of ')]
to_be_removed = ['fig.', 'lit.', 'sb ', 'sth ', ' sb', ' sth', 'to ', '...', '(completed action marker)' ]
to_be_removed_heading = [
	'refers to ',
	'marker of ',
	'marker for ',
	'marker used '
]
to_remove_ending_punctuations = set(';.?!')

particle_checkers_starting = [
	"particle expressing ",
	"particle introducing ",
	"particle marking ",
	"particle indicating ",
	"particle implying ",
	"particle intensifying ",
	"particle in old Chinese ",
	"particle similar to ",
	"particle equivalent to ",
	"particle signaling ",
	"particle for ",
	"particle used ",
	"particle placed ",
	"particle calling "
]

particle_checkers_ending = [
	"interrogative particle",
	"introductory particle",
	"grammatical particle",
	"possessive particle",
	"question particle",
	"modal particle",
	"final particle"
]

rule_for_using_pinyin = [
	"phonetic",
	"final particle",
	'postfix indicating ',
	'feminine suffix'
]

place_name_hints = [
	"Province",
	"province",
	"County",
	"county",
	"District",
	"district",
	"City",
	"city",
	"Village",
	"village",
	"Banner",
	"banner"
]

mountain_name_hints = [
	"Mt. ",
	"Mt "
]

do_not_filter = [
	"(completed action marker)"
]

def is_particle(comment):
	for checker in particle_checkers_starting:
		if checker in comment:
			return True
	for checker in particle_checkers_ending:
		if checker in comment:
			return True
	return False

def is_mountain(comment):
	for hint in mountain_name_hints:
		if comment.startswith(hint):
			return True
	return False

def is_use_pinyin(comment):
	for rule in rule_for_using_pinyin:
		if rule in comment:
			return True
	return False

def get_starting_namelike_words(comment):
	cut = comment.split(' ')
	ret = []
	for word in cut:
		if len(word) != 0 and word[0].isupper():
			ret += [word]
		else:
			break
	return " ".join(ret)

def is_unwanted(comment):
	for checker in unwant_checkers:
		if checker in comment:
			return True
	return False

def is_unrelated(text, comment):
	for chkey, chcom in relation_checkers:
		if chkey not in text and chcom in comment:
			return True
	return False

def get_seealso(comment):
	alsos = set()
	also = None
	for variant in also_checkers:
		if variant in comment:
			try:
				also = comment.split(variant, 1)[1].split('[', 1)[0].split('|')
				# 找到了一种语法表达的“另见”
				break
			except IndexError:
				pass

	if also is None:
		return set()

	# 找到“另见”后，把繁中的部分翻译为简中，并返回。
	for word in also:
		try:
			alsos |= ctdict[word]
		except KeyError:
			if word in cedict:
				alsos |= {word}
	return alsos

def prune_place_name(comment):
	if comment[0].isupper() == False:
		return comment
	words = comment.split(' ')
	ret = []
	for word in words:
		ret += [word]
		if word in place_name_hints:
			break
	return " ".join(ret)

checked_options = set()

def get_best_random_expl(word, **kwargs):
	def check_bool_kwargs(keyword):
		global checked_options
		checked_options |= {keyword}
		try:
			return bool(kwargs[keyword])
		except KeyError:
			return False

	global pruned, extended, redirected, removed_expl, redirect_chosen
	scwords = {word}
	try:
		scwords |= ctdict[word]
	except KeyError:
		pass
	expl = lookup(word)
	if expl is None:
		return word, False
	wpy = " ".join([p[0] for p in pinyin(word, style=Style.TONE3, neutral_tone_with_five=True)])
	wpyu = wpy.upper()
	wpyn = ''.join(c for c in wpy if c.isalpha())

	# 遍历查阅到的字典项，为进行大小写不敏感的拼音查找而复制出全大写的拼音项。
	upperlook = {}
	for pron, comments in expl.items():
		upron = pron.upper()
		if upron not in expl: upperlook[upron] = comments
	expl = {**expl, **upperlook}

	# 先找到所有相关的候选词
	cand = set()
	seealsos = set()
	cand_from = {}
	raw_comments = {}

	# 先找拼音对应的，找不到就不管拼音了
	def try_match_pinyin(expl):
		try:
			comments = expl[wpy]
		except KeyError:
			try:
				comments = expl[wpyu]
			except KeyError:
				# 找不到拼音对应，则进行拼音不匹配的方式查询
				comments = []
				for pron, comm in expl.items():
					comments.extend(comm)
		return comments

	# 检查内容是不是需要的
	def check_comment(cw, comment):
		nonlocal seealsos, raw_comments
		global pruned, extended, redirected, removed_expl

		# 此处统计“已移除项”，在去掉括弧内容和逗号内容后，把释义先添加到“已移除项”里，在最后没有被排除的时候再排除。
		remo = {f"{cw} -> {comment}"}

		# 对“非另见”的释义移除进行提示。
		if cw == word: removed_expl |= remo

		def add_to_cand(cmnt):
			nonlocal cand, cand_from
			global removed_expl
			# 筛选需要的
			cand |= {cmnt}
			cand_from[cmnt] = cw # 反向查询
			removed_expl -= remo # 实际上没有被移除时，从“已移除项”里排除。

		if check_bool_kwargs('no-pinyin') == False:
			if is_use_pinyin(comment):
				raw_comments[wpyn] = comment
				add_to_cand(wpyn)
				return

		# 提取引号里的内容
		quoteds = extract_quoteds(comment)

		# 记录原始释义
		before_prune = comment

		# 去掉括弧里的内容，并截断逗号后面的内容
		if comment not in do_not_filter:
			comment = remove_parenthesis(comment, "()")
			comment = remove_parenthesis(comment, "{}")
			comment = comment.split(',', 1)[0].strip()
			comment = comment.replace('  ', ' ')

		# 如果整个释义里、不要的东西都删除后就莫得释义内容了，则从引号里的内容里寻找可能有用的内容。
		if len(comment) == 0:
			for quoted in quoteds:
				check_comment(cw, quoted)
			return
		else:
			raw_comments[comment] = before_prune

		# 去掉“particle”类型的解释，即语素描述
		if is_particle(comment):
			return

		# 去掉“另见”，但是要记录另见什么。
		seealso = get_seealso(comment)
		if len(seealso):
			seealsos |= seealso
			removed_expl -= remo
			return

		# 如果是地名，去掉不需要的部分
		comment = prune_place_name(comment)

		# 检测是否为山峰名字
		if is_mountain(comment):
			comment = get_starting_namelike_words(comment)

		# 去掉关联性匹配失败的内容
		if is_unrelated(cw, comment):
			return

		# 去掉其余不想要的内容
		if is_unwanted(comment):
			return

		# 添加至候选项
		add_to_cand(comment)

	# 找到后，处理每一个解释项，删掉不要的解释项，并记录“另见”
	for comment in try_match_pinyin(expl):
		check_comment(word, comment)

	p_relateds = set()
	while len(cand) == 0:
		# 如果没有符合条件的选项，则看看有没有合适的“另见”
		# 先把“另见”里面与当前词相同的去除
		no_seealsos = False
		while len(cand) == 0:
			# 去掉自己对自己的引用
			seealsos -= scwords
			if len(seealsos) == 0:
				no_seealsos = True
				break
			iter_seealsos = set(seealsos)
			seealsos = set()
			for also in iter_seealsos:
				alsoexpl = lookup(also)
				if alsoexpl is None:
					print(f"无法查询的“另见”条目：{also}")
					continue
				redirected |= {f"{word} -> {also}"}
				for comment in try_match_pinyin(alsoexpl):
					check_comment(also, comment)

		# 如果还没有找到符合条件的选项（没有可用的 seealsos ）则找相关词
		no_related = False
		if len(cand) == 0:
			relateds = get_related_words(word)
			relateds -= p_relateds
			if len(relateds) == 0:
				no_related = True
			else:
				extended |= {(f'{word} -> {"、".join(list(relateds)[:8])}').strip()}
				for related in relateds:
					relatedexpl = lookup(related)
					if relatedexpl is None:
						print(f"无法查询的“关联”条目：{related}")
						continue
					for comment in try_match_pinyin(relatedexpl):
						check_comment(related, comment)
				no_seealsos = True if len(seealsos) == 0 else False
			p_relateds |= set(relateds)

		# 如果既没有“另见”条目，也没有关联词，则退出循环
		if no_seealsos and no_related:
			break

	# 如果相关词里也给不出候选项，则翻译失败，返回原单词。
	if len(cand) == 0:
		return word, False

	# 准备从候选项里挑选内容
	if check_bool_kwargs('shortest'):
		# 挑选最短候选项
		chcom = sorted(cand, key=len)[0]
	elif check_bool_kwargs('longest'):
		# 挑选最长候选项
		chcom = sorted(cand, key=len)[-1]
	else:
		# 瞎几把挑选
		chcom = random.choice(list(cand))

	# 如果发生转义查询，则找回这个释义对应的辞头
	try:
		chword = cand_from[chcom]
		if word != chword:
			redirect_chosen |= {f"{word} -> {chword}"}
			word = chword
	except KeyError:
		pass

	# 挑选后，删除不需要的字符串内容
	try:
		before_prune = raw_comments[chcom]
	except KeyError:
		before_prune = chcom
	for wr in to_be_removed:
		chcom = chcom.replace(wr, '')
	for wr in to_be_removed_heading:
		#if chcom.startswith(wr):
		#	chcom = chcom[len(wr):].strip()
		chcom = chcom.split(wr, 1)[0]
	if before_prune != chcom:
		pruned |= {f"{word}：{before_prune} -> {chcom}"}
	return chcom, True

punct_replace_rule = {
	'，': ',',
	'。': '.',
	'、': ',',
	'“': '"',
	'”': '"',
	'‘': "'",
	'’': "'",
	'【': '[',
	'】': ']'
}

full2half_d = dict((i + 0xFEE0, i) for i in range(0x21, 0x7F))
full2half_d[0x3000] = 0x20
for zhp, enp in punct_replace_rule.items():
	full2half_d[ord(zhp)] = ord(enp)
def full2half(f2h):
	return f2h.translate(full2half_d)

def merge_translation_result(trans):
	texbuf, tranbuf = '', ''
	prev_is_translated = True
	result = []
	for text, tran in trans:
		if text == tran:
			texbuf += text
			tranbuf += tran
			prev_is_translated = False
		else:
			if not prev_is_translated:
				result += [(texbuf, tranbuf)]
				texbuf, tranbuf = '', ''
				prev_is_translated = True
			result += [(text, tran)]
	if not prev_is_translated:
		result += [(texbuf, tranbuf)]
	return result

def madtran(text, **kwargs):
	global checked_options
	checked_options |= {'custom-rules'}
	try:
		custom_rules = kwargs['custom-rules']
	except KeyError:
		custom_rules = {}
	fccr = {w[0] for w in custom_rules.keys()}
	crw_sorted = sorted(custom_rules.keys(), key=len, reverse=True)
	def check_bool_kwargs(keyword):
		global checked_options
		checked_options |= {keyword}
		try:
			return bool(kwargs[keyword])
		except KeyError:
			return False
	def do_dismantle(ch):
		try:
			dismantle = random.choice(zipart[ch])
			dismantle = remove_parenthesis(dismantle, '()')
			dismantle = remove_parenthesis(dismantle, '{}')
			dismantle = dismantle.replace('#', '')
			dismantle = dismantle.strip()
			if len(dismantle) == 0:
				return ch
			else:
				return dismantle
		except KeyError:
			return ch
	# 根据可能的词语长度，截取输入的句子来查字典找释义。
	if check_bool_kwargs("by-char"):
		search_range = range(cedict_maxkeylen + 1)
	else:
		search_range = [8, 7, 6, 5, 4, 3, 2, 1]
		search_range += list(range(max(search_range) + 1, cedict_maxkeylen + 1))
	trans = []
	text = text.replace('\n', ' ')
	# 如果用户要求拆字，则先拆字再翻译
	if check_bool_kwargs("dismantle"):
		dismantled = ""
		while len(text):
			dismantled += do_dismantle(text[0])
			text = text[1:]
		text = dismantled
	while len(text):
		# 过滤标点符号等字典里没有的东西
		if text[0] not in firstchars and text[0] not in fccr:
			if text[0] not in zipart:
				# 英文或者标点符号等，直接略过
				word = text[0]
				trans += [(word, full2half(word))]
				text = text[1:]
				continue
			else:
				# 丈育发生——字典里没有这个字，但是 IDS 数据库里有，那就拆字！
				unknown = text[0]
				dismantle = do_dismantle(unknown)
				if dismantle == unknown:
					word = unknown
					trans += [(word, full2half(word))]
					text = text[1:]
					print(f'遇到不认识的汉字「{unknown}」。')
				else:
					text = dismantle + text[1:]
					print(f'遇到不认识的汉字「{unknown}」，拆成偏旁部首「{dismantle}」')
				continue
		# 先从自定义规则里开始查
		crw_hit = False
		for crw in crw_sorted:
			if text.startswith(crw):
				trans += [(crw, custom_rules[crw])]
				text = text[len(crw):]
				crw_hit = True
				break
		if crw_hit: continue
		# 进行遍历查词，从最短的词开始查。
		for wl in search_range:
			word = text[:wl]
			tran, status = get_best_random_expl(word, **kwargs)
			if status == False:
				wl += 1
			else:
				trans += [(word, tran)]
				text = text[wl:]
				status = True
				break
		# 没查到，则直接把单字作为结果（跳过这个字）。
		if status == False:
			word = text[0]
			trans += [(word, full2half(word))]
			text = text[1:]
			continue
	# 翻译出结果后，除最后一个单词，其余的单词的释义里的一些句尾符号要去除
	for i in range(len(trans) - 1):
		text, tran = trans[i]
		if full2half(text) == tran: continue
		# 如果原单词里不包含标点，那么应当去除翻译后的单词里的标点
		if len(set(text) & to_remove_ending_punctuations) == 0:
			for punctuation in to_remove_ending_punctuations:
				tran = tran.replace(punctuation, ' ')
			trans[i] = (text, tran.strip())
	return merge_translation_result(trans)

def get_result_string(trans):
	def remove_double_spaces(text):
		while "  " in text:
			text = text.replace("  ", " ")
		return text
	def punctuation_spacing(text, punctuation = ','):
		return text.replace(' ' + punctuation, punctuation).replace(punctuation + ' ', punctuation).replace(punctuation, punctuation + ' ').strip()
	result = ""
	for word, tran in trans:
		if word == tran:
			result += word
		else:
			if len(tran):
				if tran[0] not in ['~', '-']:
					result += " " + tran + " "
				else:
					result = result.strip() + tran[1:].strip() + " "
	result = remove_double_spaces(result.strip())
	result = punctuation_spacing(result, ',')
	result = punctuation_spacing(result, '.')
	result = punctuation_spacing(result, '!')
	result = punctuation_spacing(result, '?')
	if len(result) and result[-1].isalpha():
		result += '.'
	return result

class redirect_std_streams(object):
	def __init__(self, stdout=None, stderr=None):
		self._stdout = stdout or sys.stdout
		self._stderr = stderr or sys.stderr

	def __enter__(self):
		self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
		self.old_stdout.flush(); self.old_stderr.flush()
		sys.stdout, sys.stderr = self._stdout, self._stderr
		os.environ['HTTP_PROXY'] = HTTP_PROXY
		os.environ['HTTPS_PROXY'] = HTTPS_PROXY

	def __exit__(self, exc_type, exc_value, traceback):
		self._stdout.flush(); self._stderr.flush()
		sys.stdout = self.old_stdout
		sys.stderr = self.old_stderr
		del os.environ['HTTP_PROXY']
		del os.environ['HTTPS_PROXY']

if __name__ == '__main__':
	import googletrans
	from httpcore import SyncHTTPProxy

	def usage():
		print("用法：madtran [--shortest|--longest] [--no-ai] [--no-pinyin] [--verbose] [--by-char] [--only-result] [--only-ai-result] [--only-result-tb] [--only-ai-result-tb] [--custom-rules=a:b,c:d] <中文内容>")
		print("参数：")
		print("  --help：显示此帮助")
		print("  --shortest：选用最短候选词")
		print("  --longest：选用最长候选词")
		print("  --dismantle：强制对每个输入的汉字进行莽夫式拆解")
		print("  --no-ai：不进行AI修正")
		print("  --no-pinyin：不进行拼音语素检查")
		print("  --verbose：显示查询的具体过程")
		print("  --by-char：进行逐字查词")
		print("  --only-result：仅输出结果句子")
		print("  --only-result-tb：仅输出结果句子被谷歌翻译回的中文句子")
		print("  --only-ai-result：仅输出 AI 纠正后的结果句子")
		print("  --only-ai-result-tb：仅输出 AI 纠正后的结果句子被谷歌翻译回的中文句子")
		print("  --custom-rules：指定自定义规则，特定单词按自定义规则进行翻译。规则内容格式例：蟹:rust,答辩:fecet")
		print("使用`CEDict`中英字典，对中文内容进行一个查字典式的翻译，然后使用AI语法纠正器纠正语法，进行一个莽夫式强行翻译。")
		print("莽夫式翻译可以模拟一个不会中文的人（手上却有中英字典）通过查字典进行逐词翻译，然后瞎几把选择释义（因为看不懂）造句。")
		print("造句后，句子很可能是语法不对的，于是使用现代赛博科技人工智能英语语法纠正器对句子的语法进行一个纠正。")
		print("纠正后，自动使用谷歌翻译再给翻译回中文，以对比翻译效果。")
		exit()

	text = ""
	options = {}
	for argi in range(1, len(sys.argv)):
		arg = sys.argv[argi]
		if arg.startswith('--'):
			akv = arg[2:].split('=', 1)
			if len(akv) < 2: akv += ['True']
			ak, av = akv
			options[ak] = av
		else:
			text = " ".join(sys.argv[argi:])
			break
	def check_bool_options(keyword):
		global checked_options
		checked_options |= {keyword}
		try:
			return bool(options[keyword])
		except KeyError:
			return False
	def check_any_bool_options(*keywords):
		for usages in keywords:
			if check_bool_options(usages):
				return True
		return False

	if len(text) == 0 or check_bool_options('help'):
		usage()

	wrongly_usages = []
	def check_arg_conflict(*conflist_args):
		global wrongly_usages
		confliction = set()
		for arg in conflist_args:
			if check_bool_options(arg):
				confliction |= {arg}
		if len(confliction) > 1:
			wrongly_usages += [confliction]

	check_arg_conflict('verbose', 'only-result', 'only-result-tb', 'only-ai-result', 'only-ai-result-tb')
	check_arg_conflict('no-ai', 'only-ai-result', 'only-ai-result-tb')
	if len(wrongly_usages):
		for confliction in wrongly_usages:
			print(f'--{"、--".join(confliction)} 用法冲突。')
		exit()

	if 'custom-rules' in options:
		try:
			options['custom-rules'] = { w.strip(): c.strip() for w, c in [rule.split(':', 1) for rule in options['custom-rules'].split(',')]}
		except:
			print('解析自定义翻译规则失败。自定义翻译规则的格式应当是每条规则使用冒号分隔单词和释义，并用逗号分隔多条规则。如果需要插入空格则需要使用双引号把整个命令行参数（包括`--custom-rules=`在内）包起来。')
			exit()

	clean_output = check_any_bool_options('only-result', 'only-result-tb', 'only-ai-result', 'only-ai-result-tb')
	if not clean_output:
		print("正在进行莽夫式翻译。")

	# 我们的按词翻译方案
	trans = madtran(text, **options)
	tranwords = "|".join(["空格" if "".join(kv) == '  ' else kv[0] if kv[1] == "" else "%s -> %s" % kv for kv in trans])
	result_string = get_result_string(trans)

	if check_bool_options("only-result"):
		print(result_string)
		exit()

	# 检查是否有输出，有输出才使用谷歌翻译
	if len(result_string) == 0:
		if not clean_output:
			print(f"原文：{text}")
			print("原始结果：<空>")
		exit()

	if USE_PROXY:
		proxy = SyncHTTPProxy((b"http", PROXY_ADDR.encode('utf-8'), PROXY_PORT, b""))
		proxies = {"http" : proxy, "https" : proxy}
	else:
		proxies = None
	if 'HTTP_PROXY' in os.environ: del os.environ['HTTP_PROXY']
	if 'HTTPS_PROXY' in os.environ: del os.environ['HTTPS_PROXY']
	translator = googletrans.Translator(proxies=proxies)

	def get_translated(text):
		global translator
		try:
			return translator.translate(text, dest='zh-cn').text
		except:
			return "调用谷歌翻译失败。"

	def get_corrected(text):
		retry = 0
		why_retry = None
		while retry < 3:
			try:
				with redirect_std_streams(stdout=sys.stderr):
					return Caribe.caribe_corrector(text)
			except Exception as e:
				if why_retry is None: why_retry = str(e)
				retry += 1
		return f'AI 自动纠正失败：{why_retry}'

	translated_nc = get_translated(result_string)
	if check_bool_options("only-result-tb"):
		print(translated_nc)
		exit()

	if not clean_output:
		print("已完成莽夫式翻译。")
		print(f"原文：{text}")
		def show_comment(comset, prompt, delim='，'):
			try:
				if len(comset):
					print(f"{prompt}{delim.join(sorted(list(comset)))}")
			except TypeError:
				pass
		if check_bool_options('verbose'):
			show_comment(extended, "扩展查询：")
			show_comment(removed_expl, "移除的字典释义：\n* ", '\n* ')
			show_comment(redirected, "转义查询：")
			show_comment(redirect_chosen, "采用的转义查询：")
			show_comment(pruned, "释义简化：\n* ", '\n* ')
		print(f"莽夫式翻译结果：\n{tranwords}")

	if check_bool_options('no-ai') == False:
		if not clean_output:
			print("AI语法纠正：")
			print(f"纠正前：{result_string}")
			print(f"谷歌翻译：{translated_nc}")
			print("正在对生成的英文句子进行 AI 纠正。")

		corrected = get_corrected(result_string)
		if check_bool_options("only-ai-result"):
			print(corrected)
			exit()
		translated_co = get_translated(corrected)
		if check_bool_options("only-ai-result-tb"):
			print(translated_co)
			exit()
		if result_string.lower() != corrected.lower() and translated_nc != translated_co:
			print(f"纠正后：{corrected}")
			print(f"谷歌翻译：{translated_co}")
		else:
			print("纠正后结果与纠正前一致。")
	else:
		print(f"生成句子：{result_string}")
		print(f"谷歌翻译：{translated_nc}")

	unchecked_options = set(options.keys()) - checked_options
	if len(unchecked_options):
		print("未知选项：--" + "，--".join(unchecked_options))
