#!/bin/bash
set -e

if [[ -z ${PLUGIN_CONTEXT} ]]
then
    PLUGIN_CONTEXT="."
fi

if [[ -z ${PLUGIN_FILES} ]]
then
    IMAGE_HASH=$(echo ${DRONE_COMMIT_AFTER} | head -c7)
else
    IMAGE_HASH=""
    for file in $(echo ${PLUGIN_FILES} | sed -e "s/,/ /g")
    do
        IMAGE_HASH=${IMAGE_HASH}$(md5sum ${file} | head -c7)
    done
fi

if [[ ! -z ${PLUGIN_USERNAME} ]]
then
    if [[ -z ${PLUGIN_REGISTRY} ]]
    then
        docker login -u ${PLUGIN_USERNAME} -p ${PLUGIN_PASSWORD} > /dev/null 2>&1
    else
        docker login -u ${PLUGIN_USERNAME} -p ${PLUGIN_PASSWORD} ${PLUGIN_REGISTRY} > /dev/null 2>&1
    fi
fi
set +e
docker pull ${PLUGIN_REPO}:${IMAGE_HASH}
RESPONSE=$?
set -e

if [[ ${RESPONSE} -ne 0 ]]
then
    docker build -t ${PLUGIN_REPO}:${IMAGE_HASH} -t ${PLUGIN_REPO}:testing -f ${PLUGIN_DOCKERFILE} ${PLUGIN_CONTEXT}
    docker push ${PLUGIN_REPO}:${IMAGE_HASH}
    docker push ${PLUGIN_REPO}:testing
fi
if [[ "${PLUGIN_FORCETAG}" == "true" ]]
then
    if [[ -z ${PLUGIN_TAGS} ]]
    then
        if [[ ${DRONE_BRANCH} == *"fullCI-"* ]]
        then
            PLUGIN_TAGS="testing"
        else
            PLUGIN_TAGS="${DRONE_BRANCH}"
        fi
    fi
    current_tag=${IMAGE_HASH}
    for tag in $(echo ${PLUGIN_TAGS} | sed -e "s/,/ /g")
    do
        docker tag ${PLUGIN_REPO}:${current_tag} ${PLUGIN_REPO}:${PLUGIN_TAG}
        docker push ${PLUGIN_REPO}:${PLUGIN_TAG}
    done
fi

exit 0
