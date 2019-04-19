# Drone Image Manager Plugin
Plugin for the [DroneCI solution](https://drone.io) in order to pull or build an image.

This plugin can be used to add a pipeline or step layer for building, publishing, or simply pulling a dependency
layer image for a project as well as an application layer.

## Context

This plugin is to respond to the need of wanting faster drone builds by multi-layering the environment build
of a project.

As well as accelerating builds, this ensures that the environments themselves with all necessary dependencies
are saved to easily revert back if ever there is an issue.

## Example usage

Given a Python code project with all dependencies being stored inside a `requirements.txt` file, a dependency layer
could be as the following `deps.Dockerfile`:

```docker
FROM python:3.6.8-slim-stretch

RUN mkdir -p /app

COPY requirements.txt /app/.

RUN pip install -U pip setuptools wheel

ENV PIP_WHEEL_DIR=/wheelhouse \
    WHEELHOUSE=/wheelhouse \
    PIP_FIND_LINKS=/wheelhouse

WORKDIR /app

RUN pip wheel numpy \
    && while read p; do pip wheel $p; done < requirements.txt
```

This image would be used within the projects main Dockerfile image as so:

```docker
FROM myrepo/mypythonimage-deps:latest

WORKDIR /app

RUN while read p; do pip install --no-index -f /wheelhouse $p; done < requirements.txt \
  && rm -rf /wheelhouse
 
# Rest of Dockerfile commands
[...]
```

This way, the environment is downloaded and built only if the `requirements.txt` file is changed.
This is maintained by collecting the md5 hashsum of the requirement files and using them as the image tag.
The plugin checks if the image tag hashsum already exists, if so, it simply pulls the image for future usage during the
drone build, otherwise, the plugin builds the image with the hashsum image tag and any tag given as a parameter
(`latest` in our example) so that the main Dockerfile can pull the image without needing to calculate the hash itself. 

Multiple dependency files can be used to constitute the hashsum tag.
Given the following example with a NodeJS project using `package.json` and `package-lock.json`:

```docker
FROM node:10.15.0

RUN mkdir -p /app

WORKDIR /app

COPY package-lock.json /app/.
COPY package.json /app/.

RUN npm ci
```

The main project image could be the following:

```docker
FROM myrepo/mynodeimage-deps:latest

COPY . /app/.

EXPOSE 80

ENTRYPOINT ["npm", "run"]
CMD ["start"]
```
 
The below pipeline configuration demonstrates simple usage of the plugin:

```yaml
steps:
- name: pull_or_build_deps
  image: galea/drone-tools:builder
  settings:
    repo: galea
    image: mypython-image-deps
    files:
     - deps.Dockerfile
     - requirements.txt
    tags:
     - latest
    dockerfile: ./deps.Dockerfile
  volumes: # Necessary to retain the image over all pipelines
  - name: docker_socket
    path: /var/run/docker.sock
```

## Parameter Reference

- **image**:

    Image name for the dependency layer

- **files**:

    List of files to be used for the checksum image tag

- **tags**:

    List of tag to be used during publish

- **push_tags**: *Default:* `false`

    Boolean to indicate weather or not to push images to the registry after the build.

- **force_tag**:

    If specified, this single tag will override image hash building and become the publish tag for the image.

- **dockerfile**:

    Path and name to the Dockerfile used to build the dependency layer

- **context**: *Default:* `.`

    Build context sent to `docker build`.

- **args**:

    Build args sent to `docker build`.

- **registry**: *Default:* `docker.io`

    Registry to be used for pull/push of the image.

- **repo**:

    Repository to be used for pull/push of the image.

- **login**: *Default:* `false`

    Registry requires login.

- **username**:

    Username for the registry.

- **password**:

    Password for the registry (used with username)

- **commands**:

    List of shell commands to execute right before terminating the script.

- **commands_only**: *Default:* `false`

    Ignore normal execution, run the list of commands then exit. No building, pulling or pushing.