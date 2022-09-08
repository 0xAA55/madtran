#!/usr/bin/env python3
# -*- coding: utf-8 -*
import os
import sys
import json
import time
import random
import Caribe # 需要 Python 有 sqlite3 模块且能安装 torch
from pypinyin import pinyin, Style

USE_PROXY = True
PROXY_ADDR = "localhost"
PROXY_PORT = 1080

if __name__ == '__main__':
	cedict_url = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.zip"
	def makepath(filename):
		return os.path.join(os.path.dirname(os.path.realpath(__file__)), filename)
	cedict_zipfile = makepath("cedict_1_0_ts_utf-8_mdbg.zip")
	cedict_member = "cedict_ts.u8"
	cedict_srcfile = makepath("cedict.txt")
	cedict_pyfile = makepath("cedict_database.py")
	if os.path.exists(cedict_pyfile) and time.time() - os.path.getmtime(cedict_pyfile) > 86400:
		print("正在更新字典。")
		os.remove(cedict_pyfile)
		if os.path.exists(cedict_zipfile):
			os.remove(cedict_zipfile)
			if os.path.exists(cedict_member):
				os.remove(cedict_member)
				if os.path.exists(cedict_srcfile):
					os.remove(cedict_srcfile)

	if not os.path.exists(cedict_pyfile):
		if not os.path.exists(cedict_zipfile):
			import requests
			if USE_PROXY:
				proxies = {
					"http": "socks5h://%s:%d" % (PROXY_ADDR, PROXY_PORT),
					"https": "socks5h://%s:%d" % (PROXY_ADDR, PROXY_PORT)
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
				print("下载字典失败：%d：%s" % (resp.status_code, resp.content))
				exit()

		if not os.path.exists(cedict_srcfile):
			import zipfile
			with zipfile.ZipFile(cedict_zipfile, 'r') as z:
				z.extract(cedict_member)
			os.rename(cedict_member, cedict_srcfile)

		print("正在解析CEDict")
		import subprocess
		subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.realpath(__file__)), "cedict_parse.py")])

from cedict_database import ctdict, cedict, firstchars, cedict_maxkeylen

full2half = dict((i + 0xFEE0, i) for i in range(0x21, 0x7F))
full2half[0x3000] = 0x20
extended = set()
removed_expl = set()

def remove_parenthesis(comments, parenthesis="()"):
	result = ""
	while True:
		cut = comments.split(parenthesis[0], 1)
		result += cut[0] + " "
		if len(cut) == 2:
			try:
				comments = cut[1].split(parenthesis[1], 1)[1] + " "
			except IndexError:
				break
		else:
			break
	return result.replace("  ", " ").strip()

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
unwant_checkers = [ 'CL:', 'pr.', 'used in ', 'used before ', 'abbr. ', '[', ']', '|', 'classifier for ', 'interjection of ' ]
relation_checkers = [('单', 'unit of ')]
to_be_removed = [ 'fig.', 'lit.', 'sb', 'sth', '...' ]
to_remove_ending_punct = set(';.?!')

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

def is_particle(comment):
	for checker in particle_checkers_starting:
		if checker in comment:
			return True
	for checker in particle_checkers_ending:
		if checker in comment:
			return True
	return False

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

def get_best_random_expl(word):
	global extended, removed_expl
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
	# 遍历查阅到的字典项，为进行大小写不敏感的拼音查找而复制出全大写的拼音项。
	upperlook = {}
	for pron, comments in expl.items():
		upron = pron.upper()
		if upron not in expl: upperlook[upron] = comments
	expl = {**expl, **upperlook}
	# 先找到所有相关的候选词
	cand = set()
	seealsos = set()

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
	def check_comment(comment):
		nonlocal cand, seealsos
		global extended, removed_expl

		# 去掉括弧里的内容，并截断逗号后面的内容
		comment = remove_parenthesis(comment, "()")
		comment = remove_parenthesis(comment, "{}")
		comment = comment.split(',', 1)[0].strip()
		comment = comment.replace('  ', ' ')
		if len(comment) == 0:
			return

		# 此处统计“已移除项”，在去掉括弧内容和逗号内容后，把释义先添加到“已移除项”里，在最后没有被排除的时候再排除。
		remo = {"%s -> %s" % (word, comment)}
		removed_expl |= remo

		# 去掉“particle”类型的解释，即语素描述
		if is_particle(comment):
			return

		# 去掉“另见”，但是要记录另见什么。
		seealso = get_seealso(comment)
		if len(seealso):
			seealsos |= seealso
			return

		# 去掉关联性匹配失败的内容
		if is_unrelated(word, comment):
			return

		# 去掉其余不想要的内容
		if is_unwanted(comment):
			return

		# 筛选需要的
		cand |= {comment}
		removed_expl -= remo # 实际上没有被移除时，从“已移除项”里排除。

	# 找到后，处理每一个解释项，删掉不要的解释项，并记录“另见”
	for comment in try_match_pinyin(expl):
		check_comment(comment)

	# 如果没有符合条件的选项，则看看有没有合适的“另见”
	# 先把“另见”里面与当前词相同的去除
	while len(cand) == 0:
		seealsos - scwords
		if len(seealsos) == 0:
			break
		iter_seealsos = set(seealsos)
		for also in iter_seealsos:
			alsoexpl = lookup(also)
			if alsoexpl is None:
				print("无用 also 内容：%s" % (also))
				continue
			for comment in try_match_pinyin(alsoexpl):
				check_comment(comment)
		seealsos |= iter_seealsos

	# 如果还没有找到符合条件的选项（没有可用的 seealsos ）则找相关词
	if len(cand) == 0:
		relateds = get_related_words(word)
		if len(relateds):
			extended |= {("%s -> %s" % (word, "、".join(list(relateds)[:8]))).strip()}
		for related in relateds:
			relatedexpl = lookup(related)
			if relatedexpl is None:
				print("无用 related 内容：%s" % (related))
				continue
			for comment in try_match_pinyin(relatedexpl):
				check_comment(comment)

	# 如果相关词里也给不出候选项，则翻译失败，返回原单词。
	if len(cand) == 0:
		return word, False

	# 否则从剩下的候选项里，瞎几把挑一个。
	word = random.choice(list(cand))
	for wr in to_be_removed:
		word = word.replace(wr, '')
	return word, True

def madtran(text):
	# 根据可能的词语长度，截取输入的句子来查字典找释义。
	search_range = [2, 3, 4, 5, 1] + list(range(6, cedict_maxkeylen + 1))
	trans = []
	text = text.replace('\n', ' ')
	while len(text):
		# 过滤标点符号等字典里没有的东西
		if text[0] not in firstchars:
			trans += [(text[0], text[0].translate(full2half))]
			text = text[1:]
			continue
		# 进行遍历查词，从最短的词开始查。
		for wl in search_range:
			word = text[:wl]
			tran, status = get_best_random_expl(word)
			if status == False:
				wl += 1
			else:
				trans += [(word, tran)]
				text = text[wl:]
				status = True
				break
		# 没查到，则直接把单字作为结果（跳过这个字）。
		if status == False:
			trans += [(text[0], text[0].translate(full2half))]
			text = text[1:]
			continue
	# 翻译出结果后，除最后一个单词，其余的单词的释义里的一些句尾符号要去除
	for i in range(len(trans) - 1):
		text, tran = trans[i]
		if text == tran: continue
		# 如果原单词里不包含标点，那么应当去除翻译后的单词里的标点
		if len(set(text) & to_remove_ending_punct) == 0:
			for punct in to_remove_ending_punct:
				tran = tran.replace(punct, ' ')
			trans[i] = (text, tran.strip())
	return trans

def get_result_string(trans):
	result = ""
	for word, tran in trans:
		if word == tran:
			result += word
		else:
			result += " " + tran + " "
	while "  " in result:
		result = result.replace("  ", " ")
	return result.strip()

def usage():
	print("用法：madtran <中文内容>")
	print("使用`CEDict`中英字典，对中文内容进行一个查字典式的翻译，然后使用AI语法纠正器纠正语法，进行一个莽夫式强行翻译。")
	print("强行翻译后，自动使用谷歌翻译再给翻译回中文，以对比翻译效果。")
	exit()

class redirect_std_streams(object):
    def __init__(self, stdout=None, stderr=None):
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush(); self.old_stderr.flush()
        sys.stdout, sys.stderr = self._stdout, self._stderr

    def __exit__(self, exc_type, exc_value, traceback):
        self._stdout.flush(); self._stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

if __name__ == '__main__':
	import googletrans
	from httpcore import SyncHTTPProxy
	text = " ".join(sys.argv[1:])
	if len(text) == 0:
		usage()

	# 我们的按词翻译方案
	trans = madtran(text)
	tranwords = "|".join(["%s -> %s" % kv if "".join(kv) != '  ' else "空格" for kv in trans])
	result_string = get_result_string(trans)

	# 检查是否有输出
	if len(result_string) == 0:
		print("原文：%s" % (text))
		print("原始结果：<空>")
		exit()

	# 进行一个句子纠正
	print("已完成莽夫式翻译，正在进行AI纠正。")
	with redirect_std_streams(stdout=sys.stderr):
		corrected = Caribe.caribe_corrector(result_string)
		#corrected = result_string

	# 再用正经翻译软件翻译回来
	if USE_PROXY:
		proxy = SyncHTTPProxy((b"http", PROXY_ADDR.encode('utf-8'), PROXY_PORT, b""))
		proxies = {"http" : proxy, "https" : proxy}
	else:
		proxies = None
	translator = googletrans.Translator(proxies=proxies)
	try:
		translated = translator.translate(corrected, dest='zh-cn').text
	except:
		translated = "调用谷歌翻译失败。"

	print("原文：%s" % (text))
	def show_comment(comset, prompt, delim='，'):
		try:
			if len(comset):
				print("%s%s" % (prompt, delim.join(comset)))
		except TypeError:
			pass
	show_comment(extended, "扩展查询：")
	show_comment(removed_expl, "移除的字典释义：", '\n')
	print("莽夫式翻译结果：\n%s" % (tranwords))

	if len(result_string) >= 200:
		print("AI语法纠正：%s" % (corrected))
	else:
		print("AI语法纠正：\n纠正前：%s\n纠正后：%s" % (result_string, corrected))
	print("谷歌翻译：%s" % (translated))
