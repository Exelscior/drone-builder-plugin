#!/bin/bash
set -e

[[ -z ${PLUGIN_CONTEXT} ]] && PLUGIN_CONTEXT="."
[[ -z ${PLUGIN_PUSHTAGS} ]] && PLUGIN_PUSHTAGS="true"
[[ -z ${PLUGIN_COMMITTAG} ]] && PLUGIN_COMMITTAG="true"


if [[ ${PLUGIN_DEBUG} == "true" ]]
then
    OLD_IFS=${IFS}
    IFS=$'\n'
    for variable in $(env)
    do
        key=${variable%%"="*}
        value=${variable#*"="}
        if [[ ${key} == *"PLUGIN"* ]]
        then
            name=$(echo ${key#*"_"} | tr "[:upper:]" "[:lower:]")
            [[ ${name} != *"password"* ]] \
              && echo "${name[*]^}: ${value}" \
              || echo "Password: $(echo ${PLUGIN_PASSWORD} | sed -e 's/./*/g')"
        fi
    done
    IFS=${OLD_IFS}
fi

if [[ ! -z ${PLUGIN_COMMANDS} ]]
then
    for cmd in $(echo ${PLUGIN_COMMANDS} | sed -e "s/,/ /g")
    do
        [[ ${PLUGIN_DEBUG} == "true" ]] && echo "Executing command '${cmd}'"
        /bin/bash -c ${cmd}
    done
    exit $?
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
[[ ${PLUGIN_DEBUG} == "true" ]] && echo "Image hash: ${IMAGE_HASH}"

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
docker pull ${PLUGIN_REPO}:${IMAGE_HASH} > /dev/null 2>&1
RESPONSE=$?
set -e

if [[ ${RESPONSE} -ne 0 ]]
then
    echo "Image not found. Building."
    build_args=""
    if [[ ! -z ${PLUGIN_ARGS} ]]
    then
        for arg in $(echo ${PLUGIN_ARGS} | sed -e "s/,/ /g")
        do
            key=${arg%%"="*}
            value=${arg#*"="}
            value=$(echo ${value} | grep -q "{{.*}}" \
                && new_value=$(env | grep $(echo ${value} | sed -rn "s/\{\{(.*?)\}\}/\1/p")) \
                && echo ${new_value#*"="} \
                || echo ${value})
            build_args="${build_args} --build-arg ${key}=${value}"
        done
    fi
    if [[ ${PLUGIN_DEBUG} == "true" ]]
    then
        echo docker build --no-cache --force-rm -t ${PLUGIN_REPO}:${IMAGE_HASH} -t ${PLUGIN_REPO}:testing ${build_args} -f ${PLUGIN_DOCKERFILE} ${PLUGIN_CONTEXT}
    fi
    docker build --no-cache --force-rm -t ${PLUGIN_REPO}:${IMAGE_HASH} -t ${PLUGIN_REPO}:testing ${build_args} -f ${PLUGIN_DOCKERFILE} ${PLUGIN_CONTEXT}
fi
if [[ "${PLUGIN_PUSHTAGS}" == "true" ]]
then
    if [[ -z ${PLUGIN_TAGS} && ${PLUGIN_COMMITTAG} == "true" ]]
    then
        PLUGIN_TAGS=$(echo ${DRONE_BRANCH} | sed -e "s:/:-:g")
    fi
    if [[ ${PLUGIN_DEBUG} == "true" ]]
    then
        echo docker push ${PLUGIN_REPO}:${IMAGE_HASH}
        echo docker push ${PLUGIN_REPO}:testing
    fi
    docker push ${PLUGIN_REPO}:${IMAGE_HASH}
    docker push ${PLUGIN_REPO}:testing
    current_tag=${IMAGE_HASH}
    for tag in $(echo ${PLUGIN_TAGS} | sed -e "s/,/ /g")
    do
        if [[ ${PLUGIN_DEBUG} == "true" ]]
        then
            echo docker tag ${PLUGIN_REPO}:${current_tag} ${PLUGIN_REPO}:${PLUGIN_TAG}
            echo docker push ${PLUGIN_REPO}:${PLUGIN_TAG}
        fi
        docker tag ${PLUGIN_REPO}:${current_tag} ${PLUGIN_REPO}:${PLUGIN_TAG}
        docker push ${PLUGIN_REPO}:${PLUGIN_TAG}
    done
fi

exit 0
