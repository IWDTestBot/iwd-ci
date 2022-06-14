#!/bin/bash

export PYTHONPATH=$GITHUB_WORKSPACE/cibase
export WORKDIR=$GITHUB_WORKSPACE/workdir

export

mkdir $WORKDIR

git config --global user.name "$GITHUB_ACTOR"
git config --global user.email "$GITHUB_ACTOR@users.noreply.github.com"

#DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata
#apt -y install iputils-ping gitlint isc-dhcp-client

if [ $GITHUB_EVENT_NAME == 'pull_request' ]
then
	PR=${GITHUB_REF#"refs/pull/"}
	PR=${PR%"/merge"}
	PR="-p $PR"
else
	PR=''
fi

python3 $GITHUB_WORKSPACE/iwd-ci/run-ci.py $PR -c $GITHUB_WORKSPACE/iwd-ci/config.ini -r $GITHUB_REPO -s $GITHUB_WORKSPACE/iwd -e $GITHUB_WORKSPACE/ell -v
