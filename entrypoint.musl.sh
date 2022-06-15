#!/bin/sh

export PYTHONPATH=$GITHUB_WORKSPACE/cibase
export WORKDIR=$GITHUB_WORKSPACE/workdir
#export GITHUB_TOKEN=$1
#export EMAIL_TOKEN=$2
#export PATCHWORK_TOKEN=$3
export

mkdir $WORKDIR

git config --global user.name "$GITHUB_ACTOR"
git config --global user.email "$GITHUB_ACTOR@users.noreply.github.com"
git remote set-url origin "https://x-access-token:$GITHUB_TOKEN@github.com/$GITHUB_REPOSITORY"

if [ $GITHUB_EVENT_NAME == 'pull_request' ]
then
	PR=${GITHUB_REF#"refs/pull/"}
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

python3 $GITHUB_WORKSPACE/cibase/cibase.py $EX_TRIGGER $PR -c /config.musl.ini \
		-r IWDTestBot/iwd -s $GITHUB_WORKSPACE/iwd \
		-e $GITHUB_WORKSPACE/ell -v
