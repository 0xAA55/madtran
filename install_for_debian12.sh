#!/bin/bash

echo Installing dependencies for python 3.9.23
sudo apt-get -y install build-essential zlib1g-dev libbz2-dev liblzma-dev libncurses5-dev libreadline6-dev libsqlite3-dev libssl-dev libgdbm-dev liblzma-dev tk-dev lzma lzma-dev libgdbm-dev

echo Installing pyenv
curl -fsSL https://pyenv.run | bash

echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc

export PYENV_ROOT="$HOME/.pyenv
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"

export PYTHON_CONFIGURE_OPTS="--enable-loadable-sqlite-extensions --disable-ipv6"
pyenv install 3.9.23
pyenv local 3.9.23

python -m pip install -U pip
python -m pip install -r requirements.txt
