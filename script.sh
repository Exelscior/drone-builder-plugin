#!/bin/bash
set -e

IMAGE_HASH=""
for file in $(echo ${PLUGIN_FILES} | sed -e "s/,/ /g")
do
    IMAGE_HASH=${IMAGE_HASH}$(md5sum ${file} | head -c7)
done

if [[ -z ${PLUGIN_TAG} ]]
then
    if [[ ${DRONE_BRANCH} == *"fullCI-"* ]]
    then
        PLUGIN_TAG="testing"
    else
        PLUGIN_TAG="${DRONE_BRANCH}"
    fi
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
docker pull ${PLUGIN_IMAGE}:${IMAGE_HASH}
RESPONSE=$?
set -e

if [[ ${RESPONSE} -ne 0 ]]
then
    docker build -t ${PLUGIN_IMAGE}:${IMAGE_HASH} -t ${PLUGIN_IMAGE}:${PLUGIN_TAG} -f ${PLUGIN_DOCKERFILE} .
    docker push ${PLUGIN_IMAGE}:${IMAGE_HASH}
    docker push ${PLUGIN_IMAGE}:${PLUGIN_TAG}
else
    if [[ "${PLUGIN_FORCETAG}" == "true" ]]
    then
        docker tag ${PLUGIN_IMAGE}:${IMAGE_HASH} ${PLUGIN_IMAGE}:${PLUGIN_TAG}
        docker push ${PLUGIN_IMAGE}:${PLUGIN_TAG}
    fi
fi

exit 0
