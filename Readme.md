# Madtran: Mad Translation（莽夫翻译器）

使用`CEDict`中英字典，对中文内容进行一个查字典式的翻译，然后使用AI语法纠正器纠正语法，进行一个莽夫式强行翻译。
强行翻译后，自动使用谷歌翻译再给翻译回中文，以对比翻译效果。

在尝试查字典翻译时，如果遇到了查不到释义的生僻字，则使用 [IDS](https://github.com/yi-bai/ids.git) 数据库对汉字进行偏旁部首的莽夫式拆分，试图通过拆偏旁部首来猜出生僻字的含义。

中英字典：[CEDict](https://www.mdbg.net/chinese/dictionary?page=cc-cedict)

CEDICT - Copyright (C) 1997, 1998 Paul Andrew Denisowski

AI语法纠正器：[Caribe](https://pypi.org/project/Caribe/)

## 安装依赖项：

首先你要有 `Python 3.6` 以及更新的版本，并且它应当具备 `sqlite3` 模块（被 `Caribe` 依赖），并且能安装 `torch`。

运行以下命令：

	pip install -r requirements.txt

## 注意事项

使用谷歌翻译的过程中需要你的网络能够访问到谷歌。修改 `madtran.py` 第 11...13 行的代码，设置你自己的 http 或 socks 代理，默认使用 `localhost:1080`。
*如果你没有 socks 代理，而是使用 VPN 形式的代理，或者路由器内置代理，则应当将 `USE_PROXY` 设置为 `False`。*
*如果不想使用谷歌翻译，可以尝试删除所有 `googletrans` 相关代码。*

AI 语法纠正器使用的是 `Caribe` 方案，因此：
*如果你的 Python 环境是使用 pyenv 在 Linux 环境搭建的（自己编译 Python），你需要有 `libsqlite3-dev` 或者 `sqlite3-devel`*
*不推荐使用 pypy 解释器来运行此脚本，因为 `Caribe` 依赖 `torch`，而 pypy 安装 `torch` 非常折腾*
*如果不想使用 AI 语法纠正器，可以尝试删除所有 `Caribe` 相关代码。*

## 使用方法：

可直接运行。

	python madtran.py 测试翻译的句子

初次运行时，Caribe 会需要下载它依赖的神经网络等内容。
每次翻译时，若同一个单词具有多个候选项，则会使用随机数进行随机抽选。

## 示例输出：

运行：

	python madtran.py 测试翻译的句子

输出内容：

	正在进行莽夫式翻译。
	已完成莽夫式翻译。
	原文：测试翻译的句子
	莽夫式翻译结果：
	测试 -> a test|翻译 -> interpretation|的 -> of|句子 -> sentence
	AI语法纠正：
	纠正前：a test interpretation of sentence.
	谷歌翻译：句子的测试解释。
	正在对生成的英文句子进行 AI 纠正。
	纠正后结果与纠正前一致。

运行：

	python madtran.py 几号抽签啊

输出内容：

	正在进行莽夫式翻译。
	已完成莽夫式翻译。
	原文：几号抽签啊
	莽夫式翻译结果：
	几号 -> heroin|抽签 -> perform divination with sticks|啊 -> My goodness!
	AI语法纠正：
	纠正前：heroin perform divination with sticks My goodness!
	谷歌翻译：海洛因用棍子表演占卜！
	正在对生成的英文句子进行 AI 纠正。
	纠正后：Hero performs divination with sticks My goodness!
	谷歌翻译：英雄用棍棒表演占卜！

运行：

	python madtran.py 草草草

输出内容：

	正在进行莽夫式翻译。
	已完成莽夫式翻译。
	原文：草草草
	莽夫式翻译结果：
	草草 -> carelessly|草 -> manuscript
	AI语法纠正：
	纠正前：carelessly manuscript.
	谷歌翻译：粗心的手稿。
	正在对生成的英文句子进行 AI 纠正。
	纠正后结果与纠正前一致。

运行：

	python madtran.py 我倒是不懂那些东西

输出内容：

	正在进行莽夫式翻译。
	已完成莽夫式翻译。
	原文：我倒是不懂那些东西
	莽夫式翻译结果：
	我 -> I|倒是 -> contrariwise|不 -> not so|懂 -> comprehend|那些 -> those|东西 -> east and west
	AI语法纠正：
	纠正前：I contrariwise not so comprehend those east and west.
	谷歌翻译：相反，我不太了解那些东西方。
	正在对生成的英文句子进行 AI 纠正。
	纠正后：I contrariwise do not comprehend those east and west.
	谷歌翻译：相反，我不理解那些东西方。
