#! /bin/bash

# Script that sets various environmental variables for the rest of the CI pipeline.
# Common vars used to make bigger, exported env vars.
# EDIT THESE VARS HERE if you're a fork maintainer.
REPO_OWNER="arneschwarck"
REPO_NAME="openpilot"
REPO="$REPO_OWNER/$REPO_NAME"
REGISTRY_BASE="ghcr.io"
MAIN_BRANCH="master"
TEMP_IMAGE="tmppilotci"
UNIT_TEST="coverage run --append -m unittest discover"

CONTAINER_URI="$REGISTRY_BASE/$REPO/openpilot"
BASE_IMAGE="$CONTAINER_URI-base:latest"
CI_IMAGE="${CONTAINER_URI}ci:latest"
FAT_IMAGE="$CONTAINER_URI-fat:latest"

LOGIN="docker login $REGISTRY_BASE -u $REPO_OWNER -p"
RUN_CMD_BASE="docker run --shm-size 1G -e PYTHONPATH=/tmp/openpilot -e GITHUB_ACTION -e GITHUB_REF -e GITHUB_HEAD_REF -e GITHUB_SHA -e GITHUB_REPOSITORY -e GITHUB_RUN_ID -v /tmp/comma_download_cache:/tmp/comma_download_cache"

# Local vars, generally don't change these.
__eval_true='true'
__eval_false='' # Empty string because non-empty string are always true (at least for github actions / workflows)
__ref_prefix="refs/heads/"

# Functions
function eval_var()
{
    local __result_var=$1

    if [[ $2 = $3 ]]; then
        local __result=$__eval_true
    else
        local __result=$__eval_false
    fi

    eval $__result_var="$__result"
}

# Evaluate Environment
eval_var IS_DEFAULT $GITHUB_REPOSITORY $REPO
eval_var IS_MAIN $GITHUB_REF "$__ref_prefix$MAIN_BRANCH"

if [[ $GITHUB_EVENT_NAME = 'push' && $IS_DEFAULT = $__eval_true && $IS_MAIN = $__eval_true ]]; then
    MAIN_IMAGE="$FAT_IMAGE"
    BUILD_CMD="docker build -t $BASE_IMAGE -f Dockerfile.openpilot_base . && docker build -t $CI_IMAGE -f Dockerfile.openpilotci --cache-from $BASE_IMAGE . && docker build -t $FAT_IMAGE -f Dockerfile.openpilot_fat --cache-from $CI_IMAGE ."
    RUN_CMD="$RUN_CMD_BASE --name $TEMP_IMAGE"
    SHOULD_BUILD_DOCKER='true'
else
    MAIN_IMAGE="$CI_IMAGE"
    BUILD_CMD="docker pull $CI_IMAGE"
    RUN_CMD="$RUN_CMD_BASE -v $PWD:/tmp/openpilot --rm"
    SHOULD_BUILD_DOCKER=''
fi

RUN_CMD="$RUN_CMD $MAIN_IMAGE /bin/sh -c"
HEAD_BRANCH=$(basename $GITHUB_REF)

# Export Environment
echo "IS_DEFAULT_REPO=$IS_DEFAULT" >> $GITHUB_ENV
echo "IS_MAIN_BRANCH=$IS_MAIN" >> $GITHUB_ENV

echo "HEAD_BRANCH=$HEAD_BRANCH" >> $GITHUB_ENV
echo "MAIN_BRANCH=$MAIN_BRANCH" >> $GITHUB_ENV

echo "CONTAINER_URI=$CONTAINER_URI" >> $GITHUB_ENV

echo "BASE_IMAGE=$BASE_IMAGE" >> $GITHUB_ENV
echo "CI_IMAGE=$CI_IMAGE" >> $GITHUB_ENV
echo "FAT_IMAGE=$FAT_IMAGE" >> $GITHUB_ENV
echo "MAIN_IMAGE=$MAIN_IMAGE" >> $GITHUB_ENV
echo "TEMP_IMAGE=$TEMP_IMAGE" >> $GITHUB_ENV

echo "BUILD_CMD=$BUILD_CMD" >> $GITHUB_ENV
echo "RUN_CMD=$RUN_CMD" >> $GITHUB_ENV

echo "SHOULD_BUILD_DOCKER=$SHOULD_BUILD_DOCKER" >> $GITHUB_ENV
echo "DOCKER_LOGIN=$LOGIN" >> $GITHUB_ENV
