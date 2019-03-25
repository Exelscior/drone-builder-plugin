#!/bin/bash
set -e

IMAGE_HASH=""
for file in $(echo ${PLUGIN_FILES} | sed -e "s/,/ /g")
do
  IMAGE_HASH=${IMAGE_HASH}$(md5sum ${file} | head -c7)
done

set +e
docker pull ${PLUGIN_IMAGE}:${IMAGE_HASH}
RESPONSE=$?
set -e

if [[ $RESPONSE -ne 0 ]]
then
  docker build -t ${PLUGIN_IMAGE}:${IMAGE_HASH} -t ${PLUGIN_IMAGE}:${PLUGIN_TAG} -f ${PLUGIN_DOCKERFILE} .
  docker push ${PLUGIN_IMAGE}:${IMAGE_HASH}
  docker push ${PLUGIN_IMAGE}:${PLUGIN_TAG}
fi

exit 0
