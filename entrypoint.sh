#!/bin/bash

export PYTHONPATH=$GITHUB_WORKSPACE/cibase
export WORKDIR=$GITHUB_WORKSPACE/workdir

export

mkdir $WORKDIR

git config --global user.name "$GITHUB_ACTOR"
git config --global user.email "$GITHUB_ACTOR@users.noreply.github.com"

#DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata
#apt -y install iputils-ping gitlint isc-dhcp-client

if [ $REF_BRANCH != 'refs/heads/workflow' ]
then
	PR=${REF_BRANCH#"refs/pull/"}
	PR=${PR%"/merge"}
	PR="-p $PR"
else
	PR=''
fi

if [ $GITHUB_REPO != $GITHUB_REPOSITORY ]
then
	EX_TRIGGER="-x"
else
	EX_TRIGGER=""
fi

python3 $GITHUB_WORKSPACE/iwd-ci/run-ci.py $EX_TRIGGER $PR -c $GITHUB_WORKSPACE/iwd-ci/config.ini -r $GITHUB_REPO -s $GITHUB_WORKSPACE/iwd -e $GITHUB_WORKSPACE/ell -v
